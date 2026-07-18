from __future__ import annotations

import html
import importlib.util
import json
import os
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
OUT_DIR = ROOT / "output" / f"margin_weighted_seat_report_{RUN_DATE}"
DATA_DIR = OUT_DIR / "data"
MARGIN_URL = "https://qhweb.eastmoney.com/bzj/allexchange"
MARGIN_CACHE_DIR = ROOT / "data"
MARGIN_CACHE_REF = MARGIN_CACHE_DIR / "margin_reference.csv"
MARGIN_CACHE_STATUS = MARGIN_CACHE_DIR / "margin_fetch_status.csv"
MARGIN_CACHE_DAYS = 7
TREND_TEMP_DIR = ROOT / "data"
TREND_ACTIVE_TEMPERATURES = {"温", "热", "沸", "凉", "寒", "冻"}
BULL_TEMPERATURES = {"温", "热", "沸"}
BEAR_TEMPERATURES = {"凉", "寒", "冻"}

DOMESTIC_BROKERS = ["国泰君安", "东证期货", "永安期货", "海通期货", "浙商期货", "中财期货", "南华期货", "申银万国", "中信期货", "光大期货", "一德期货", "瑞达期货", "银河期货"]
FOREIGN_BROKERS = ["高盛期货", "摩根大通", "瑞银期货"]
FAMILY_BROKERS = ["东方财富", "徽商期货", "方正中期", "华安期货", "中信建投", "广发期货", "民生期货", "平安期货", "中泰期货"]

GROUPS = {
    "内资": DOMESTIC_BROKERS,
    "外资": FOREIGN_BROKERS,
    "家人": FAMILY_BROKERS,
}

INDEX_NAMES = {
    "IH": "上证50",
    "IF": "沪深300",
    "IC": "中证500",
    "IM": "中证1000",
    "STAR50": "科创50",
    "GEM50": "创业板50",
}
INDEX_FUTURE_SYMBOLS = {"IH", "IF", "IC", "IM"}

AMOUNT_FIELDS = [
    "add_long_amount",
    "reduce_long_amount",
    "add_short_amount",
    "reduce_short_amount",
    "bull_amount",
    "bear_amount",
    "amount_score",
    "activity_amount",
    "long_chg_amount",
    "short_chg_amount",
    "long_pos_amount",
    "short_pos_amount",
    "prev_long_pos_amount",
    "prev_short_pos_amount",
    "gross_pos_amount",
]


def load_base_module():
    spec = importlib.util.spec_from_file_location("futures_report_base", ROOT / "scripts" / "generate_futures_report.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/generate_futures_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base_module()


class MarginTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict] = []
        self.current_table: dict | None = None
        self.in_target_table = False
        self.in_title = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.update_parts: list[str] = []
        self.in_update = False

    @staticmethod
    def classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        value = next((value or "" for key, value in attrs if key == "class"), "")
        return set(value.split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = self.classes(attrs)
        if "update" in classes:
            self.in_update = True
        if tag == "table":
            self.in_target_table = {"market_table", "t_table"}.issubset(classes) and "blank_table" not in classes
            if self.in_target_table:
                self.current_table = {"exchange": "", "rows": []}
        if not self.in_target_table:
            return
        if "market_title" in classes:
            self.in_title = True
        if tag == "tr":
            self.in_row = True
            self.row = []
        if tag == "td" and self.in_row:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self.in_update:
            self.update_parts.append(text)
        if self.in_target_table and self.in_title and self.current_table is not None:
            self.current_table["exchange"] += text
        if self.in_target_table and self.in_cell:
            self.cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.row.append(" ".join(self.cell_parts))
            self.in_cell = False
        if tag == "tr" and self.in_row:
            if self.current_table is not None and self.row:
                self.current_table["rows"].append(self.row)
            self.in_row = False
        if self.in_title and tag in {"div", "span", "th", "td"}:
            self.in_title = False
        if self.in_update and tag in {"div", "span", "p"}:
            self.in_update = False
        if tag == "table" and self.in_target_table:
            if self.current_table is not None:
                self.tables.append(self.current_table)
            self.current_table = None
            self.in_target_table = False

    @property
    def update_text(self) -> str:
        return " ".join(self.update_parts)


def symbol_from_contract(contract: str) -> str:
    match = re.match(r"([A-Za-z]+)", str(contract or "").strip())
    return match.group(1).upper() if match else str(contract or "").strip().upper()


def fetch_margin_reference() -> tuple[pd.DataFrame, pd.DataFrame]:
    if os.environ.get("FORCE_MARGIN_REFRESH") != "1" and MARGIN_CACHE_REF.exists() and MARGIN_CACHE_STATUS.exists():
        cache_age = datetime.now() - datetime.fromtimestamp(MARGIN_CACHE_REF.stat().st_mtime)
        if cache_age <= timedelta(days=MARGIN_CACHE_DAYS):
            ref = pd.read_csv(MARGIN_CACHE_REF, encoding="utf-8-sig")
            status = pd.read_csv(MARGIN_CACHE_STATUS, encoding="utf-8-sig")
            status = status.copy()
            status["note"] = "CACHE_WEEKLY"
            status["cache_file"] = MARGIN_CACHE_REF.as_posix()
            status["cache_age_days"] = round(cache_age.total_seconds() / 86400, 2)
            return ref, status

    req = Request(MARGIN_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", "replace")

    parser = MarginTableParser()
    parser.feed(text)
    update_text = parser.update_text
    rows: list[dict] = []

    for table in parser.tables:
        exchange = str(table.get("exchange", ""))
        for cells in table.get("rows", []):
            if len(cells) < 4:
                continue
            raw_margin = cells[2]
            margin_match = re.search(r"[-+]?\d+(?:\.\d+)?", raw_margin.replace(",", ""))
            if not margin_match:
                continue
            contract = cells[1].strip()
            rows.append(
                {
                    "source": "东方财富期货保证金表",
                    "source_url": MARGIN_URL,
                    "source_update": update_text,
                    "exchange": exchange,
                    "variety": cells[0].strip(),
                    "contract": contract,
                    "symbol": symbol_from_contract(contract),
                    "margin_per_lot": float(margin_match.group(0)),
                    "margin_rate": cells[3].strip(),
                    "note": cells[4].strip() if len(cells) > 4 else "",
                    "is_new_contract": contract.upper().endswith("F") or "新" in cells[0],
                }
            )

    raw = pd.DataFrame(rows)
    if raw.empty:
        status = pd.DataFrame(
            [
                {
                    "source": "东方财富期货保证金表",
                    "source_url": MARGIN_URL,
                    "source_update": update_text,
                    "rows": 0,
                    "note": "EMPTY",
                }
            ]
        )
        return raw, status

    by_symbol = raw.sort_values(["symbol", "is_new_contract", "contract"]).drop_duplicates("symbol", keep="first").copy()
    status = pd.DataFrame(
        [
            {
                "source": "东方财富期货保证金表",
                "source_url": MARGIN_URL,
                "source_update": update_text,
                "rows": len(raw),
                "symbols": by_symbol["symbol"].nunique(),
                "note": "OK",
            }
        ]
    )
    MARGIN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    by_symbol.to_csv(MARGIN_CACHE_REF, index=False, encoding="utf-8-sig")
    status.to_csv(MARGIN_CACHE_STATUS, index=False, encoding="utf-8-sig")
    return by_symbol, status


def fetch_position_rows() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    reuse_dir = ROOT / "output" / f"institutional_seat_report_{RUN_DATE}" / "data"
    all_rows_path = reuse_dir / "contract_rows_all.csv"
    rows_path = all_rows_path if all_rows_path.exists() else reuse_dir / "contract_rows.csv"
    status_path = reuse_dir / "fetch_status.csv"
    if os.environ.get("REFETCH_POSITIONS") != "1" and rows_path.exists():
        rows = pd.read_csv(rows_path)
        if status_path.exists():
            status = pd.read_csv(status_path)
        else:
            status = pd.DataFrame(columns=["group", "broker", "date", "rows", "url", "note"])
        return rows, status, f"复用 {rows_path.as_posix()}"

    rows: list[dict] = []
    status_rows: list[dict] = []
    for group, brokers in GROUPS.items():
        for broker in brokers:
            try:
                date, url, broker_rows = BASE.fetch_broker(broker)
                status_rows.append({"group": group, "broker": broker, "date": date, "rows": len(broker_rows), "url": url, "note": "OK"})
                for row in broker_rows:
                    item = dict(row)
                    item["group"] = group
                    rows.append(item)
            except Exception as exc:
                status_rows.append({"group": group, "broker": broker, "date": "", "rows": 0, "url": "", "note": f"ERROR: {exc}"})
    return pd.DataFrame(rows), pd.DataFrame(status_rows), "实时抓取 broker/position"


def add_flow_and_amounts(rows: pd.DataFrame, margin_ref: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows

    df = rows.copy()
    for col in ["long_pos", "long_chg", "short_pos", "short_chg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["symbol"] = df["symbol"].astype(str).str.upper()

    df["add_long"] = df["long_chg"].clip(lower=0)
    df["reduce_long"] = (-df["long_chg"]).clip(lower=0)
    df["add_short"] = df["short_chg"].clip(lower=0)
    df["reduce_short"] = (-df["short_chg"]).clip(lower=0)
    df["bull_flow"] = df["add_long"] + df["reduce_short"]
    df["bear_flow"] = df["reduce_long"] + df["add_short"]
    df["flow_score"] = df["bull_flow"] - df["bear_flow"]
    df["prev_long_pos"] = df["long_pos"] - df["long_chg"]
    df["prev_short_pos"] = df["short_pos"] - df["short_chg"]
    df["net_pos"] = df["long_pos"] - df["short_pos"]
    df["gross_pos"] = df["long_pos"] + df["short_pos"]

    join_cols = ["symbol", "margin_per_lot", "margin_rate", "exchange", "contract", "variety", "source_update"]
    ref = margin_ref[join_cols].rename(columns={"contract": "margin_contract", "variety": "margin_variety"})
    df = df.merge(ref, on="symbol", how="left")
    df["margin_per_lot"] = pd.to_numeric(df["margin_per_lot"], errors="coerce")
    df["margin_missing"] = df["margin_per_lot"].isna()
    df["margin_per_lot"] = df["margin_per_lot"].fillna(0)

    for base_col in ["add_long", "reduce_long", "add_short", "reduce_short", "long_chg", "short_chg", "long_pos", "short_pos", "prev_long_pos", "prev_short_pos"]:
        df[f"{base_col}_amount"] = df[base_col] * df["margin_per_lot"]

    df["bull_amount"] = df["add_long_amount"] + df["reduce_short_amount"]
    df["bear_amount"] = df["reduce_long_amount"] + df["add_short_amount"]
    df["amount_score"] = df["bull_amount"] - df["bear_amount"]
    df["activity_amount"] = df["bull_amount"] + df["bear_amount"]
    df["gross_pos_amount"] = df["long_pos_amount"] + df["short_pos_amount"]
    return df


def sign(value: float | int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def direction(score: float | int) -> str:
    if score > 0:
        return "偏多"
    if score < 0:
        return "偏空"
    return "中性"


def direction_class(score: float | int) -> str:
    if score > 0:
        return "bull"
    if score < 0:
        return "bear"
    return "flat"


def money_yi(value: float | int, digits: int = 2) -> str:
    return f"{value / 100000000:+.{digits}f} 亿"


def money_abs_yi(value: float | int, digits: int = 2) -> str:
    return f"{abs(value) / 100000000:.{digits}f} 亿"


def signed_hands(value: float | int) -> str:
    return f"{int(value):+,}"


def clean_symbol(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "", str(value or ""))
    return value.upper() or "-"


def symbol_tag(variety: str, symbol: str) -> str:
    code = clean_symbol(symbol)
    if code == "-" or code == clean_symbol(variety):
        return ""
    return f"<span>{html.escape(code)}</span>"


def name_code(variety: str, symbol: str) -> str:
    return f"<b>{html.escape(str(variety))}</b>{symbol_tag(variety, symbol)}"


def sector_sort(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    selected = BASE.add_sector_columns(df)
    selected = selected.assign(_abs_score=selected[score_col].abs())
    return selected.sort_values(["sector_rank", "_abs_score"], ascending=[True, False])


def sector_header(sector: str, col_span: int, text: str) -> str:
    return f'<tr class="sector-row"><td colspan="{col_span}"><b>{html.escape(str(sector))}</b><span>{html.escape(text)}</span></td></tr>'


def sector_direction_text(df: pd.DataFrame, score_col: str, limit: int = 8) -> str:
    if df.empty or score_col not in df.columns:
        return "净多：-；净空：-"

    def names(part: pd.DataFrame) -> str:
        if part.empty:
            return "-"
        ordered = part.assign(_abs=part[score_col].abs()).sort_values("_abs", ascending=False).head(limit)
        return "、".join(str(v) for v in ordered["variety"].tolist())

    bulls = names(df[df[score_col] > 0])
    bears = names(df[df[score_col] < 0])
    return f"净多：{bulls}；净空：{bears}"


def trend_stage(temperature: str) -> str:
    return {
        "温": "多头左侧预警",
        "热": "多头右侧确认",
        "沸": "多头极热/反转警戒",
        "凉": "空头左侧预警",
        "寒": "空头右侧确认",
        "冻": "空头极寒/反转警戒",
        "平": "平衡过滤",
    }.get(str(temperature), "未知")


def trend_sign(temperature: str) -> int:
    if temperature in BULL_TEMPERATURES:
        return 1
    if temperature in BEAR_TEMPERATURES:
        return -1
    return 0


def trend_class(temperature: str) -> str:
    sig = trend_sign(temperature)
    if sig > 0:
        return "bull"
    if sig < 0:
        return "bear"
    return "flat"


def load_trend_temperature() -> tuple[pd.DataFrame, str]:
    candidates = [
        TREND_TEMP_DIR / f"trend_temperature_{RUN_DATE}.csv",
        TREND_TEMP_DIR / "trend_temperature_latest.csv",
    ]
    source_path = next((path for path in candidates if path.exists()), None)
    if source_path is None:
        return pd.DataFrame(), "未找到趋势温度文件 data/trend_temperature_latest.csv"

    try:
        trend = pd.read_csv(source_path)
    except Exception as exc:
        return pd.DataFrame(), f"趋势温度读取失败：{exc}"

    required = {"symbol", "variety", "temperature", "strength"}
    missing = required - set(trend.columns)
    if missing:
        return pd.DataFrame(), f"趋势温度字段缺失：{', '.join(sorted(missing))}"

    trend = trend.copy()
    trend["symbol"] = trend["symbol"].astype(str).str.upper().str.strip()
    trend["variety"] = trend["variety"].astype(str).str.strip()
    trend["temperature"] = trend["temperature"].astype(str).str.strip()
    trend["strength"] = pd.to_numeric(trend["strength"], errors="coerce").fillna(0)
    trend["trend_sign"] = trend["temperature"].map(trend_sign)
    trend["trend_stage"] = trend["temperature"].map(trend_stage)
    trend["active_trend"] = trend["temperature"].isin(TREND_ACTIVE_TEMPERATURES)
    trend["trend_source_file"] = str(source_path)
    if "snapshot_date" not in trend.columns:
        trend["snapshot_date"] = ""
    source_values = set(trend.get("source", pd.Series(dtype=str)).dropna().astype(str))
    snapshot_dates = sorted(set(trend["snapshot_date"].dropna().astype(str)) - {""})
    if "trend_animal_api" in source_values:
        date_text = snapshot_dates[-1] if snapshot_dates else "-"
        return trend, f"趋势动物 API 直接事实：{date_text}；文件 {source_path.name}"
    return trend, f"趋势温度来源：{source_path.name}"


def trend_signal_frame(resonance: pd.DataFrame, trend: pd.DataFrame) -> pd.DataFrame:
    if trend.empty:
        return pd.DataFrame()
    active = trend[trend["active_trend"]].copy()
    if active.empty:
        return pd.DataFrame()

    keep_cols = [
        "symbol",
        "combined_amount_signal",
        "institutional_amount_score",
        "family_reverse_amount_score",
        "resonance_label",
    ]
    if resonance.empty:
        merged = active.copy()
        for col in keep_cols[1:]:
            merged[col] = 0 if col != "resonance_label" else ""
    else:
        keep = resonance[[col for col in keep_cols if col in resonance.columns]].copy()
        merged = active.merge(keep, on="symbol", how="left")
        for col in ["combined_amount_signal", "institutional_amount_score", "family_reverse_amount_score"]:
            if col not in merged.columns:
                merged[col] = 0
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
        if "resonance_label" not in merged.columns:
            merged["resonance_label"] = ""
        merged["resonance_label"] = merged["resonance_label"].fillna("")

    merged = BASE.add_sector_columns(merged)
    merged["fund_sign"] = merged["combined_amount_signal"].map(sign)

    def relation(row: pd.Series) -> str:
        if row["fund_sign"] == 0:
            return "资金未验证"
        if row["fund_sign"] == row["trend_sign"]:
            return "资金顺势"
        return "资金逆势"

    merged["trend_fund_relation"] = merged.apply(relation, axis=1)
    merged["trend_score"] = merged["strength"] * 100000000 + merged["combined_amount_signal"].abs()
    return merged.sort_values(["trend_sign", "strength", "combined_amount_signal"], ascending=[False, False, False])


def trend_summary_cards(trend_frame: pd.DataFrame, trend_status: str) -> str:
    if trend_frame.empty:
        return f'<div class="card accent"><div class="k">趋势温度</div><div class="v flat">-</div><div class="s">{html.escape(trend_status)}</div></div>'
    bull_count = int((trend_frame["trend_sign"] > 0).sum())
    bear_count = int((trend_frame["trend_sign"] < 0).sum())
    aligned = int((trend_frame["trend_fund_relation"] == "资金顺势").sum())
    contrary = int((trend_frame["trend_fund_relation"] == "资金逆势").sum())
    return f"""
      <div class="card"><div class="k">趋势温度样本</div><div class="v">{len(trend_frame)}</div><div class="s">{html.escape(trend_status)}；平指标已过滤。</div></div>
      <div class="card"><div class="k">多头趋势</div><div class="v red">{bull_count}</div><div class="s">温为左侧预警，热为右侧确认，沸为极热警戒。</div></div>
      <div class="card"><div class="k">空头趋势</div><div class="v green">{bear_count}</div><div class="s">凉为左侧预警，寒为右侧确认，冻为极寒警戒。</div></div>
      <div class="card accent"><div class="k">资金关系</div><div class="v">{aligned}/{contrary}</div><div class="s">顺势 / 逆势；资金口径为三方净金额。</div></div>
    """


def trend_temperature_rows(trend_frame: pd.DataFrame, limit: int = 24) -> str:
    if trend_frame.empty:
        return '<tr><td colspan="11" class="muted-text">暂无趋势温度数据；请更新 data/trend_temperature_latest.csv。</td></tr>'
    selected = trend_frame.sort_values(["strength", "combined_amount_signal"], ascending=[False, False]).head(limit)
    selected = sector_sort(selected, "trend_score")
    max_money = max(selected["combined_amount_signal"].abs().max(), 1)
    rows = []
    current_sector = None
    for _, row in selected.iterrows():
        if row["sector"] != current_sector:
            current_sector = row["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            rows.append(sector_header(current_sector, 11, sector_direction_text(sector_part, "combined_amount_signal")))
        temp = str(row["temperature"])
        rel = str(row["trend_fund_relation"])
        rel_class = "bull" if rel == "资金顺势" and row["trend_sign"] > 0 else ("bear" if rel == "资金顺势" and row["trend_sign"] < 0 else ("flat" if rel == "资金未验证" else "gold"))
        right_side = row.get("is_trend_right_side", "")
        right_label = "右侧" if str(right_side).lower() in {"true", "1", "是"} else ("非右侧" if str(right_side).lower() in {"false", "0", "否"} else "未提供")
        days = row.get("days_since_trend_entry", "")
        day_label = f"{int(days)} 天" if pd.notna(days) and str(days) != "" else "-"
        phase = str(row.get("trend_phase_curr", "") or "-")
        previous_temp = str(row.get("trend_temperature_prev", "") or "-")
        strength_change = row.get("trend_strength_local_change", "")
        change_label = f"{float(strength_change):+.2f}" if pd.notna(strength_change) and str(strength_change) != "" else "-"
        return_1d = row.get("return_1d", "")
        return_label = f"{float(return_1d):+.6f}" if pd.notna(return_1d) and str(return_1d) != "" else "-"
        rows.append(
            f"""
            <tr>
              <td>{name_code(row['variety'], row['symbol'])}</td>
              <td><span class="trend-temp {trend_class(temp)}">{html.escape(temp)}</span><span>{html.escape(str(row['trend_stage']))}</span></td>
              <td><span class="pill {'bull' if right_label == '右侧' else 'flat'}">{right_label}</span><span>{day_label}</span></td>
              <td><b>{html.escape(phase)}</b><span>{html.escape(previous_temp)} → {html.escape(temp)}</span></td>
              <td class="num">{float(row['strength']):.2f}<span>{change_label}</span></td>
              <td class="num">{return_label}</td>
              <td><span class="pill {rel_class}">{html.escape(rel)}</span></td>
              <td>{signed_amount_bar(row['combined_amount_signal'], max_money)}<span class="{direction_class(row['combined_amount_signal'])}">{money_yi(row['combined_amount_signal'])}</span></td>
              <td class="num {direction_class(row['institutional_amount_score'])}">{money_yi(row['institutional_amount_score'])}</td>
              <td class="num {direction_class(row['family_reverse_amount_score'])}">{money_yi(row['family_reverse_amount_score'])}</td>
              <td>{html.escape(str(row.get('resonance_label', '') or '-'))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def stock_index_frame(index_resonance: pd.DataFrame, trend: pd.DataFrame) -> pd.DataFrame:
    base = pd.DataFrame(
        [{"symbol": symbol, "variety": INDEX_NAMES[symbol]} for symbol in ["IH", "IF", "IC", "IM"]]
    )
    amount_cols = [
        "symbol",
        "combined_amount_signal",
        "institutional_amount_score",
        "family_reverse_amount_score",
        "resonance_label",
    ]
    if not index_resonance.empty:
        available = [col for col in amount_cols if col in index_resonance.columns]
        base = base.merge(index_resonance[available], on="symbol", how="left")

    trend_cols = [
        "symbol",
        "temperature",
        "strength",
        "trend_stage",
        "trend_sign",
        "return_1d",
        "snapshot_date",
        "source",
    ]
    index_trend = pd.DataFrame(columns=trend_cols)
    if not trend.empty:
        index_trend = trend[trend["symbol"].isin(INDEX_NAMES)].copy()
        for col in trend_cols:
            if col not in index_trend.columns:
                index_trend[col] = ""
        index_trend = index_trend[trend_cols].drop_duplicates("symbol", keep="last")
        extra = index_trend[index_trend["symbol"].isin(["STAR50", "GEM50"])][["symbol"]].copy()
        if not extra.empty:
            extra["variety"] = extra["symbol"].map(INDEX_NAMES)
            base = pd.concat([base, extra], ignore_index=True).drop_duplicates("symbol", keep="first")
        base = base.merge(index_trend, on="symbol", how="left")

    for col in ["combined_amount_signal", "institutional_amount_score", "family_reverse_amount_score"]:
        if col not in base.columns:
            base[col] = 0
        base[col] = pd.to_numeric(base[col], errors="coerce")
    for col in ["temperature", "trend_stage", "snapshot_date", "source", "resonance_label"]:
        if col not in base.columns:
            base[col] = ""
        base[col] = base[col].fillna("")
    if "trend_sign" not in base.columns:
        base["trend_sign"] = 0
    base["trend_sign"] = pd.to_numeric(base["trend_sign"], errors="coerce").fillna(0)
    return base


def stock_index_rows(index_frame: pd.DataFrame) -> str:
    if index_frame.empty:
        return '<tr><td colspan="8" class="muted-text">暂无股指观察数据。</td></tr>'
    max_money = max(index_frame["combined_amount_signal"].abs().max(skipna=True) or 0, 1)
    rows = []
    for _, row in index_frame.iterrows():
        has_seat = row["symbol"] in INDEX_FUTURE_SYMBOLS and pd.notna(row["combined_amount_signal"])
        money = float(row["combined_amount_signal"]) if has_seat else 0
        money_html = (
            f"{signed_amount_bar(money, max_money)}<span class=\"{direction_class(money)}\">{money_yi(money)}</span>"
            if has_seat
            else '<span class="muted-text">无对应股指期货席位</span>'
        )
        temp = str(row.get("temperature", "") or "")
        temp_html = (
            f'<span class="trend-temp {trend_class(temp)}">{html.escape(temp)}</span><span>{html.escape(str(row.get("trend_stage", "") or "-"))}</span>'
            if temp
            else '<span class="muted-text">趋势数据未更新</span>'
        )
        ret = row.get("return_1d", "")
        ret_text = f"{float(ret):+.6f}" if pd.notna(ret) and str(ret) != "" else "-"
        relation = "未验证"
        relation_cls = "flat"
        if temp and has_seat and sign(money):
            relation = "资金顺势" if sign(money) == int(row.get("trend_sign", 0)) else "资金逆势"
            relation_cls = direction_class(money) if relation == "资金顺势" else "gold"
        rows.append(
            f"""
            <tr>
              <td>{name_code(row['variety'], row['symbol'])}</td>
              <td>{money_html}</td>
              <td class="num {direction_class(row.get('institutional_amount_score', 0) if pd.notna(row.get('institutional_amount_score', 0)) else 0)}">{money_yi(row['institutional_amount_score']) if pd.notna(row.get('institutional_amount_score')) else '-'}</td>
              <td class="num {direction_class(row.get('family_reverse_amount_score', 0) if pd.notna(row.get('family_reverse_amount_score', 0)) else 0)}">{money_yi(row['family_reverse_amount_score']) if pd.notna(row.get('family_reverse_amount_score')) else '-'}</td>
              <td>{temp_html}</td>
              <td class="num">{ret_text}<span>Trend Animal API 原值</span></td>
              <td><span class="pill {relation_cls}">{relation}</span></td>
              <td>{html.escape(str(row.get('snapshot_date', '') or '-'))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def load_equity_sentiment_summary() -> dict:
    path = ROOT / "data" / f"zsxq_equity_sentiment_summary_{RUN_DATE}.json"
    if not path.exists():
        return {
            "status": "missing",
            "data_date": f"{RUN_DATE[:4]}-{RUN_DATE[4:6]}-{RUN_DATE[6:]}",
            "sample_count": 0,
            "sentiment_score": 0,
            "sentiment_label": "数据未获取",
            "confidence": "低",
            "community_summary": "未找到当日知识星球情绪摘要。",
            "nick_summary": "当日未取得 Nick 发帖或回复。",
            "methodology": "普通样本权重1，Nick样本权重2；仅按显式方向词计分。",
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "degraded",
            "data_date": "-",
            "sample_count": 0,
            "sentiment_score": 0,
            "sentiment_label": "读取失败",
            "confidence": "低",
            "community_summary": f"知识星球摘要读取失败：{exc}",
            "nick_summary": "当日未取得 Nick 发帖或回复。",
            "methodology": "普通样本权重1，Nick样本权重2；仅按显式方向词计分。",
        }


def equity_sentiment_panel(summary: dict) -> str:
    score = int(summary.get("sentiment_score") or 0)
    label = str(summary.get("sentiment_label") or "-")
    score_cls = "bull" if score > 0 else ("bear" if score < 0 else "gold")
    evidence = summary.get("evidence") or []
    evidence_html = []
    for item in evidence[:4]:
        sentiment = str(item.get("sentiment") or "neutral")
        cls = "bull" if sentiment == "bullish" else ("bear" if sentiment == "bearish" else "flat")
        evidence_html.append(
            f'<li><span class="pill {cls}">{html.escape({"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}.get(sentiment, "中性"))}</span>'
            f'{html.escape(str(item.get("excerpt") or ""))}</li>'
        )
    if not evidence_html:
        evidence_html.append('<li class="muted-text">当日没有可展示的方向样本。</li>')
    status = str(summary.get("status") or "missing")
    status_text = "读取正常" if status == "ok" else "降级/缺失"
    return f"""
    <div class="sentiment-grid">
      <div class="sentiment-score">
        <div class="k">A股社区情绪指标 <span class="pill {'bull' if status == 'ok' else 'gold'}">{status_text}</span></div>
        <div class="v {score_cls}">{score:+d}</div>
        <div class="sentiment-label {score_cls}">{html.escape(label)}</div>
        <div class="s">置信度 {html.escape(str(summary.get('confidence') or '低'))} · 样本 {int(summary.get('sample_count') or 0)} 条 · 数据日 {html.escape(str(summary.get('data_date') or '-'))}</div>
      </div>
      <div class="sentiment-copy">
        <h3>接口直接事实</h3>
        <p>{html.escape(str(summary.get('community_summary') or '-'))}</p>
        <h3>Nick 当日发帖 / 回复</h3>
        <p>{html.escape(str(summary.get('nick_summary') or '-'))}</p>
      </div>
      <div class="sentiment-copy">
        <h3>方向样本摘录</h3>
        <ul>{''.join(evidence_html)}</ul>
        <p class="hint"><b>分析判断：</b>{html.escape(label)}。{html.escape(str(summary.get('methodology') or ''))} 该指标反映社区风险偏好，不等同于股指涨跌预测。</p>
      </div>
    </div>
    """


def margin_label(value: float | int) -> str:
    return f"{int(round(value)):,}"


def marginal_label(long_chg_amount: float, short_chg_amount: float) -> str:
    long_s = sign(long_chg_amount)
    short_s = sign(short_chg_amount)
    if long_s > 0 and short_s < 0:
        return "多增空减"
    if long_s < 0 and short_s > 0:
        return "多减空增"
    if long_s > 0 and short_s > 0:
        return "多空同增"
    if long_s < 0 and short_s < 0:
        return "多空同减"
    if long_s > 0:
        return "多头增仓"
    if long_s < 0:
        return "多头减仓"
    if short_s > 0:
        return "空头增仓"
    if short_s < 0:
        return "空头减仓"
    return "边际平"


def marginal_class(label: str, fallback_score: float) -> str:
    if label in {"多增空减", "多头增仓", "空头减仓"}:
        return "bull"
    if label in {"多减空增", "多头减仓", "空头增仓"}:
        return "bear"
    return direction_class(fallback_score)


SUMMARY_COLUMNS = [
    "group",
    "variety",
    "symbol",
    "add_long",
    "reduce_long",
    "add_short",
    "reduce_short",
    "bull_flow",
    "bear_flow",
    "flow_score",
    "long_chg",
    "short_chg",
    "long_pos",
    "short_pos",
    "net_pos",
    "gross_pos",
    "margin_per_lot",
    "margin_rate",
    "margin_contract",
    "exchange",
    *AMOUNT_FIELDS,
    "rows",
    "min_date",
    "max_date",
]


def summarize_group(rows: pd.DataFrame, group: str) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    group_rows = rows[rows["group"] == group]
    if group_rows.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    agg: dict[str, tuple[str, str]] = {
        "add_long": ("add_long", "sum"),
        "reduce_long": ("reduce_long", "sum"),
        "add_short": ("add_short", "sum"),
        "reduce_short": ("reduce_short", "sum"),
        "bull_flow": ("bull_flow", "sum"),
        "bear_flow": ("bear_flow", "sum"),
        "flow_score": ("flow_score", "sum"),
        "long_chg": ("long_chg", "sum"),
        "short_chg": ("short_chg", "sum"),
        "long_pos": ("long_pos", "sum"),
        "short_pos": ("short_pos", "sum"),
        "net_pos": ("net_pos", "sum"),
        "gross_pos": ("gross_pos", "sum"),
        "margin_per_lot": ("margin_per_lot", "max"),
        "margin_rate": ("margin_rate", "first"),
        "margin_contract": ("margin_contract", "first"),
        "exchange": ("exchange", "first"),
        "rows": ("contract", "count"),
        "min_date": ("date", "min"),
        "max_date": ("date", "max"),
    }
    for col in AMOUNT_FIELDS:
        agg[col] = (col, "sum")

    summary = group_rows.groupby(["group", "variety", "symbol"], as_index=False).agg(**agg)
    summary["amount_dir"] = summary["amount_score"].map(direction)
    summary["marginal_structure"] = summary.apply(lambda r: marginal_label(r["long_chg_amount"], r["short_chg_amount"]), axis=1)
    return summary.sort_values("activity_amount", ascending=False)


def summarize_broker(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    selected = rows[rows["group"].isin(["内资", "外资"])]
    if selected.empty:
        return pd.DataFrame()
    grouped = selected.groupby(["group", "broker", "variety", "symbol"], as_index=False).agg(
        add_long_amount=("add_long_amount", "sum"),
        add_short_amount=("add_short_amount", "sum"),
        reduce_long_amount=("reduce_long_amount", "sum"),
        reduce_short_amount=("reduce_short_amount", "sum"),
        amount_score=("amount_score", "sum"),
        activity_amount=("activity_amount", "sum"),
        long_chg_amount=("long_chg_amount", "sum"),
        short_chg_amount=("short_chg_amount", "sum"),
    )
    grouped["amount_dir"] = grouped["amount_score"].map(direction)
    return grouped.sort_values(["group", "broker", "activity_amount"], ascending=[True, True, False])


def prefix_summary(summary: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(columns=["variety", "symbol"])
    keep = [c for c in summary.columns if c not in ["group"]]
    renamed = {c: f"{prefix}_{c}" for c in keep if c not in ["variety", "symbol"]}
    return summary[keep].rename(columns=renamed)


def build_resonance(domestic: pd.DataFrame, foreign: pd.DataFrame, family: pd.DataFrame) -> pd.DataFrame:
    merged = prefix_summary(domestic, "domestic").merge(prefix_summary(foreign, "foreign"), on=["variety", "symbol"], how="outer")
    merged = merged.merge(prefix_summary(family, "family"), on=["variety", "symbol"], how="outer")

    for col in merged.columns:
        if col not in {"variety", "symbol"} and not col.endswith("_date") and col not in {"domestic_margin_rate", "foreign_margin_rate", "family_margin_rate", "domestic_margin_contract", "foreign_margin_contract", "family_margin_contract", "domestic_exchange", "foreign_exchange", "family_exchange", "domestic_amount_dir", "foreign_amount_dir", "family_amount_dir", "domestic_marginal_structure", "foreign_marginal_structure", "family_marginal_structure"}:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

    for prefix in ["domestic", "foreign", "family"]:
        for col in ["amount_score", "activity_amount", "add_long_amount", "add_short_amount", "reduce_long_amount", "reduce_short_amount", "long_chg_amount", "short_chg_amount"]:
            name = f"{prefix}_{col}"
            if name not in merged.columns:
                merged[name] = 0

    merged["institutional_amount_score"] = merged["domestic_amount_score"] + merged["foreign_amount_score"]
    merged["family_reverse_amount_score"] = -merged["family_amount_score"]
    merged["combined_amount_signal"] = merged["institutional_amount_score"] + merged["family_reverse_amount_score"]
    merged["raw_three_group_amount_score"] = merged["institutional_amount_score"] + merged["family_amount_score"]
    merged["total_activity_amount"] = merged["domestic_activity_amount"] + merged["foreign_activity_amount"] + merged["family_activity_amount"]
    merged["institutional_long_chg_amount"] = merged["domestic_long_chg_amount"] + merged["foreign_long_chg_amount"]
    merged["institutional_short_chg_amount"] = merged["domestic_short_chg_amount"] + merged["foreign_short_chg_amount"]
    merged["all_long_chg_amount"] = merged["institutional_long_chg_amount"] + merged["family_long_chg_amount"]
    merged["all_short_chg_amount"] = merged["institutional_short_chg_amount"] + merged["family_short_chg_amount"]
    merged["all_position_chg_amount"] = merged["all_long_chg_amount"] + merged["all_short_chg_amount"]
    merged["institutional_marginal_structure"] = merged.apply(
        lambda r: marginal_label(r["institutional_long_chg_amount"], r["institutional_short_chg_amount"]), axis=1
    )

    def classify(row: pd.Series) -> pd.Series:
        domestic_sign = sign(row["domestic_amount_score"])
        foreign_sign = sign(row["foreign_amount_score"])
        institutional_sign = sign(row["institutional_amount_score"])
        family_reverse_sign = sign(row["family_reverse_amount_score"])
        domestic_foreign_same = domestic_sign != 0 and domestic_sign == foreign_sign
        family_reverse = institutional_sign != 0 and family_reverse_sign != 0 and institutional_sign == family_reverse_sign
        triple = domestic_foreign_same and family_reverse and domestic_sign == family_reverse_sign
        if triple:
            label = "三方偏多共振" if family_reverse_sign > 0 else "三方偏空共振"
            strength = min(abs(row["domestic_amount_score"]), abs(row["foreign_amount_score"]), abs(row["family_reverse_amount_score"]))
        elif domestic_foreign_same:
            label = "内外资偏多共振" if domestic_sign > 0 else "内外资偏空共振"
            strength = min(abs(row["domestic_amount_score"]), abs(row["foreign_amount_score"]))
        elif family_reverse:
            label = "机构与家人反向"
            strength = min(abs(row["institutional_amount_score"]), abs(row["family_reverse_amount_score"]))
        else:
            label = "分歧"
            strength = max(abs(row["domestic_amount_score"]), abs(row["foreign_amount_score"]), abs(row["family_reverse_amount_score"]))
        signal_value = row["combined_amount_signal"] if row["combined_amount_signal"] else row["institutional_amount_score"]
        return pd.Series(
            {
                "domestic_foreign_same": domestic_foreign_same,
                "family_reverse_resonance": family_reverse,
                "triple_resonance": triple,
                "resonance_label": label,
                "resonance_strength_amount": strength,
                "signal_dir": direction(signal_value),
            }
        )

    labels = merged.apply(classify, axis=1)
    merged = pd.concat([merged, labels], axis=1)
    merged = BASE.add_sector_columns(merged)
    return merged.sort_values(
        ["triple_resonance", "family_reverse_resonance", "resonance_strength_amount", "total_activity_amount"],
        ascending=[False, False, False, False],
    )


def amount_stack(long_amount: float, short_amount: float) -> str:
    total = abs(long_amount) + abs(short_amount)
    if total <= 0:
        return '<div class="stack muted"><span style="width:50%"></span><span style="width:50%"></span></div>'
    long_pct = abs(long_amount) / total * 100 if long_amount else 0
    short_pct = 100 - long_pct if short_amount else 0
    if long_amount and not short_amount:
        long_pct, short_pct = 100, 0
    if short_amount and not long_amount:
        long_pct, short_pct = 0, 100
    if long_amount:
        long_pct = max(3, long_pct)
    if short_amount:
        short_pct = max(3, short_pct)
    return f"""
    <div class="stack" title="加多 {money_abs_yi(long_amount)} / 加空 {money_abs_yi(short_amount)}">
      <span class="long" style="width:{long_pct:.1f}%"></span>
      <span class="short" style="width:{short_pct:.1f}%"></span>
    </div>
    """


def flow_bar(value: float, max_abs: float) -> str:
    max_abs = max(max_abs, 1)
    width = max(2, min(100, abs(value) / max_abs * 100)) if value else 0
    return f'<div class="flowbar"><i class="{direction_class(value)}" style="width:{width:.1f}%"></i></div>'


def signed_amount_bar(value: float, max_abs: float) -> str:
    max_abs = max(max_abs, 1)
    pct = min(50, abs(value) / max_abs * 50) if value else 0
    left = pct if value < 0 else 0
    right = pct if value > 0 else 0
    return f"""
    <div class="signedbar">
      <i class="neg" style="width:{left:.1f}%"></i>
      <em></em>
      <i class="pos" style="width:{right:.1f}%"></i>
    </div>
    """


def amount_tide_bucket(flow: float, position_chg: float) -> str:
    flow_text = "资金流入" if flow > 0 else ("资金流出" if flow < 0 else "资金平衡")
    pos_text = "增仓" if position_chg > 0 else ("减仓" if position_chg < 0 else "持仓平")
    return f"{flow_text} · {pos_text}"


def amount_tide_rows(resonance: pd.DataFrame, limit: int = 20) -> str:
    if resonance.empty:
        return '<tr><td colspan="7" class="muted-text">无可用资金潮汐数据</td></tr>'
    selected = resonance.copy()
    selected["tide_strength"] = selected["raw_three_group_amount_score"].abs() + selected["all_position_chg_amount"].abs() * 0.35
    selected = selected.sort_values("tide_strength", ascending=False).head(limit)
    selected = sector_sort(selected, "tide_strength")
    max_flow = max(selected["raw_three_group_amount_score"].abs().max(), 1)
    max_pos = max(selected["all_position_chg_amount"].abs().max(), 1)
    rows = []
    current_sector = None
    for _, row in selected.iterrows():
        if row["sector"] != current_sector:
            current_sector = row["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            rows.append(sector_header(current_sector, 7, sector_direction_text(sector_part, "raw_three_group_amount_score")))
        flow = row["raw_three_group_amount_score"]
        pos_chg = row["all_position_chg_amount"]
        rows.append(
            f"""
            <tr>
              <td>{name_code(row['variety'], row['symbol'])}</td>
              <td><span class="pill {direction_class(flow)}">{html.escape(amount_tide_bucket(flow, pos_chg))}</span></td>
              <td>{signed_amount_bar(flow, max_flow)}<span class="{direction_class(flow)}">净流 {money_yi(flow)}</span></td>
              <td>{signed_amount_bar(pos_chg, max_pos)}<span class="{direction_class(pos_chg)}">持仓 {money_yi(pos_chg)}</span></td>
              <td class="num {direction_class(row['domestic_amount_score'])}">{money_yi(row['domestic_amount_score'])}</td>
              <td class="num {direction_class(row['foreign_amount_score'])}">{money_yi(row['foreign_amount_score'])}</td>
              <td class="num {direction_class(row['family_amount_score'])}">{money_yi(row['family_amount_score'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def amount_compare_cell(row: pd.Series, prefix: str, max_abs: float) -> str:
    score = row.get(f"{prefix}_amount_score", 0)
    long_chg = row.get(f"{prefix}_long_chg_amount", 0)
    short_chg = row.get(f"{prefix}_short_chg_amount", 0)
    pos_chg = long_chg + short_chg
    return f"""
    <div class="compare-cell">
      {signed_amount_bar(score, max_abs)}
      <div class="compare-meta">
        <b class="{direction_class(score)}">{money_yi(score)}</b>
        <span>多 {money_yi(long_chg)} / 空 {money_yi(short_chg)} / 持仓 {money_yi(pos_chg)}</span>
      </div>
    </div>
    """


def institutional_net_cards(resonance: pd.DataFrame, side: str, per_sector: int = 3) -> str:
    if resonance.empty:
        return '<div class="empty">无可用数据</div>'
    working = BASE.add_sector_columns(resonance)
    score_col = "combined_amount_signal"
    if side == "bull":
        label = "三方共振净偏多"
        side_text = "净多"
        missing_text = "今天没有净多品种"
        selector = lambda part: part[part[score_col] > 0].sort_values(score_col, ascending=False).head(per_sector)
    else:
        label = "三方共振净偏空"
        side_text = "净空"
        missing_text = "今天没有净空品种"
        selector = lambda part: part[part[score_col] < 0].sort_values(score_col, ascending=True).head(per_sector)

    sector_keys = working[["sector", "sector_rank"]].drop_duplicates().sort_values("sector_rank")
    selected_parts = []
    for sector in sector_keys["sector"]:
        part = selector(working[working["sector"].eq(sector)])
        if not part.empty:
            selected_parts.append(part)
    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    max_value = max(selected[score_col].abs().max(), 1) if not selected.empty else 1
    cards = []
    for sector in sector_keys["sector"]:
        sector_part = working[working["sector"].eq(sector)]
        sector_selected = selector(sector_part)
        cards.append(
            f'<div class="sector-label"><b>{html.escape(str(sector))}</b><span>{html.escape(sector_direction_text(sector_part, score_col))}</span></div>'
        )
        if sector_selected.empty:
            cards.append(f'<div class="rank-card empty sector-empty">{html.escape(missing_text)}</div>')
            continue
        for _, row in sector_selected.iterrows():
            score = row[score_col]
            width = max(6, abs(score) / max_value * 100)
            cls = direction_class(score)
            cards.append(
                f"""
                <div class="rank-card">
                  <div class="rank-head">{name_code(row['variety'], row['symbol'])}</div>
                  <div class="rank-value {cls}">{money_yi(score)}</div>
                  <div class="rank-track"><i class="{cls}" style="width:{width:.1f}%"></i></div>
                  <div class="rank-sub">{html.escape(label)}；板块{side_text}前{per_sector}；机构 {money_yi(row['institutional_amount_score'])} / 家人反向 {money_yi(row['family_reverse_amount_score'])}</div>
                </div>
                """
            )
    return "\n".join(cards)


def group_card(summary: pd.DataFrame, label: str, css_class: str) -> str:
    if summary.empty:
        return f'<div class="card {css_class}"><div class="k">{html.escape(label)}</div><div class="v">-</div><div class="s">无可用数据</div></div>'
    net = float(summary["amount_score"].sum())
    add_long = float(summary["add_long_amount"].sum())
    add_short = float(summary["add_short_amount"].sum())
    top = summary.assign(abs_score=summary["amount_score"].abs()).sort_values("abs_score", ascending=False).head(1)
    top_text = f"{top.iloc[0]['variety']} {money_yi(top.iloc[0]['amount_score'])}" if not top.empty else "-"
    return f"""
    <div class="card {css_class}">
      <div class="k">{html.escape(label)}</div>
      <div class="v {direction_class(net)}">{money_yi(net)}</div>
      <div class="s">加多 {money_abs_yi(add_long)} / 加空 {money_abs_yi(add_short)}；最强方向：{html.escape(top_text)}</div>
    </div>
    """


def amount_rows(resonance: pd.DataFrame, limit: int = 24) -> str:
    if resonance.empty:
        return '<tr><td colspan="10" class="muted-text">无可用数据</td></tr>'
    selected = resonance.sort_values(
        ["triple_resonance", "resonance_strength_amount", "raw_three_group_amount_score"],
        ascending=[False, False, False],
    ).head(limit)
    selected = sector_sort(selected, "total_activity_amount")
    max_signal = max(
        selected["combined_amount_signal"].abs().max(),
        selected["institutional_amount_score"].abs().max(),
        selected["domestic_amount_score"].abs().max(),
        selected["foreign_amount_score"].abs().max(),
        selected["family_amount_score"].abs().max(),
        1,
    )
    selected["_sector_signal"] = selected.apply(lambda r: r["combined_amount_signal"] if r["combined_amount_signal"] else r["institutional_amount_score"], axis=1)
    rows = []
    current_sector = None
    for _, row in selected.iterrows():
        if row["sector"] != current_sector:
            current_sector = row["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            rows.append(sector_header(current_sector, 10, sector_direction_text(sector_part, "_sector_signal")))
        signal_value = row["combined_amount_signal"] if row["combined_amount_signal"] else row["institutional_amount_score"]
        marginal = row["institutional_marginal_structure"]
        marginal_cls = marginal_class(marginal, row["institutional_amount_score"])
        margin = max(row.get("domestic_margin_per_lot", 0), row.get("foreign_margin_per_lot", 0), row.get("family_margin_per_lot", 0))
        margin_contract = row.get("domestic_margin_contract") or row.get("foreign_margin_contract") or row.get("family_margin_contract") or ""
        rows.append(
            f"""
            <tr>
              <td>{name_code(row['variety'], row['symbol'])}<span>{html.escape(str(margin_contract))}</span></td>
              <td><span class="pill {direction_class(signal_value)}">{html.escape(str(row['resonance_label']))}</span></td>
              <td class="num">{margin_label(margin)}</td>
              <td>{amount_compare_cell(row, 'domestic', max_signal)}</td>
              <td>{amount_compare_cell(row, 'foreign', max_signal)}</td>
              <td>{amount_compare_cell(row, 'family', max_signal)}</td>
              <td>{signed_amount_bar(row['family_reverse_amount_score'], max_signal)}<span class="{direction_class(row['family_reverse_amount_score'])}">reverse {money_yi(row['family_reverse_amount_score'])}</span></td>
              <td><span class="pill {marginal_cls}">{html.escape(str(marginal))}</span><span>多 {money_yi(row['institutional_long_chg_amount'])} / 空 {money_yi(row['institutional_short_chg_amount'])}</span></td>
              <td>{signed_amount_bar(signal_value, max_signal)}</td>
              <td class="num {direction_class(row['raw_three_group_amount_score'])}">{money_yi(row['raw_three_group_amount_score'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def resonance_rows(resonance: pd.DataFrame, limit: int = 18) -> str:
    if resonance.empty:
        return '<tr><td colspan="8" class="muted-text">无可用数据</td></tr>'
    selected = resonance[(resonance["triple_resonance"]) | (resonance["family_reverse_resonance"])].head(limit)
    if selected.empty:
        return '<tr><td colspan="8" class="muted-text">暂无机构与家人反向后的同向共振</td></tr>'
    selected["_sector_signal"] = selected.apply(lambda r: r["combined_amount_signal"] if r["combined_amount_signal"] else r["institutional_amount_score"], axis=1)
    selected = sector_sort(selected, "resonance_strength_amount")
    rows = []
    current_sector = None
    for _, row in selected.iterrows():
        if row["sector"] != current_sector:
            current_sector = row["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            rows.append(sector_header(current_sector, 8, sector_direction_text(sector_part, "_sector_signal")))
        signal_value = row["combined_amount_signal"] if row["combined_amount_signal"] else row["institutional_amount_score"]
        rows.append(
            f"""
            <tr>
              <td>{name_code(row['variety'], row['symbol'])}</td>
              <td><span class="pill {direction_class(signal_value)}">{html.escape(str(row['resonance_label']))}</span></td>
              <td class="num {direction_class(row['domestic_amount_score'])}">{money_yi(row['domestic_amount_score'])}</td>
              <td class="num {direction_class(row['foreign_amount_score'])}">{money_yi(row['foreign_amount_score'])}</td>
              <td class="num {direction_class(row['institutional_amount_score'])}">{money_yi(row['institutional_amount_score'])}</td>
              <td class="num {direction_class(row['family_amount_score'])}">{money_yi(row['family_amount_score'])}</td>
              <td class="num {direction_class(row['family_reverse_amount_score'])}">{money_yi(row['family_reverse_amount_score'])}</td>
              <td class="num {direction_class(row['raw_three_group_amount_score'])}">{money_yi(row['raw_three_group_amount_score'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)



def broker_panel(broker_df: pd.DataFrame, broker: str) -> str:
    broker_rows = broker_df[broker_df["broker"] == broker].copy()
    if not broker_rows.empty:
        broker_rows["abs_amount_score"] = broker_rows["amount_score"].abs()
    part = broker_rows.sort_values("abs_amount_score", ascending=False).head(7) if not broker_rows.empty else broker_rows
    if part.empty:
        return f'<div class="broker-card"><h3>{html.escape(broker)}</h3><div class="empty">无数据</div></div>'
    part = sector_sort(part, "amount_score")
    max_activity = max(part["amount_score"].abs().max(), 1)
    rows = []
    current_sector = None
    for _, row in part.iterrows():
        if row["sector"] != current_sector:
            current_sector = row["sector"]
            sector_part = part[part["sector"] == current_sector]
            rows.append(f'<div class="broker-sector">{html.escape(str(current_sector))}<span>{html.escape(sector_direction_text(sector_part, "amount_score"))}</span></div>')
        width = max(4, abs(row["amount_score"]) / max_activity * 100) if row["amount_score"] else 0
        cls = direction_class(row["amount_score"])
        rows.append(
            f"""
            <div class="broker-row">
              <div>{name_code(row['variety'], row['symbol'])}</div>
              <div class="broker-meter"><i class="{cls}" style="width:{width:.1f}%"></i></div>
              <div class="num {cls}">{money_yi(row['amount_score'])}</div>
            </div>
            """
        )
    return f'<div class="broker-card"><h3>{html.escape(broker)}</h3>{"".join(rows)}</div>'


def status_cards(fetch_status: pd.DataFrame) -> str:
    if fetch_status.empty:
        return '<div class="status-row warn"><b>无抓取状态</b><span>-</span><em>-</em><strong>0 行</strong></div>'
    cards = []
    for row in fetch_status.itertuples():
        note = str(getattr(row, "note", ""))
        rows = int(getattr(row, "rows", 0) or 0)
        cls = "ok" if note == "OK" and rows > 0 else "warn"
        cards.append(
            f"""
            <div class="status-row {cls}">
              <b>{html.escape(str(row.broker))}</b>
              <span>{html.escape(str(row.group))}</span>
              <em>{html.escape(str(getattr(row, 'date', '-') or '-'))}</em>
              <strong>{rows} 行</strong>
            </div>
            """
        )
    return "\n".join(cards)


def build_html(
    rows: pd.DataFrame,
    fetch_status: pd.DataFrame,
    margin_status: pd.DataFrame,
    trend_temperature: pd.DataFrame,
    trend_status: str,
    domestic: pd.DataFrame,
    foreign: pd.DataFrame,
    family: pd.DataFrame,
    broker_summary: pd.DataFrame,
    resonance: pd.DataFrame,
    index_resonance: pd.DataFrame,
    position_source: str,
) -> str:
    dates = sorted(str(d) for d in fetch_status.get("date", pd.Series(dtype=str)).dropna().unique() if str(d))
    date_label = dates[-1] if dates else RUN_DATE
    margin_update = ""
    if not margin_status.empty:
        margin_update = str(margin_status.iloc[0].get("source_update", ""))
    used_symbols = rows["symbol"].nunique() if not rows.empty else 0
    matched_symbols = rows.loc[~rows.get("margin_missing", pd.Series(False, index=rows.index)), "symbol"].nunique() if not rows.empty else 0
    missing_symbols = sorted(rows.loc[rows.get("margin_missing", pd.Series(False, index=rows.index)), "symbol"].dropna().astype(str).unique()) if not rows.empty else []
    coverage_text = f"{matched_symbols}/{used_symbols}"

    institutional_score = float(domestic["amount_score"].sum() + foreign["amount_score"].sum()) if not domestic.empty or not foreign.empty else 0
    family_reverse_score = float(-family["amount_score"].sum()) if not family.empty else 0
    triple_count = int(resonance["triple_resonance"].sum()) if not resonance.empty else 0
    triple_bull_count = int(((resonance["triple_resonance"]) & (resonance["combined_amount_signal"] > 0)).sum()) if not resonance.empty else 0
    triple_bear_count = int(((resonance["triple_resonance"]) & (resonance["combined_amount_signal"] < 0)).sum()) if not resonance.empty else 0
    same_count = int(resonance["domestic_foreign_same"].sum()) if not resonance.empty else 0
    family_reverse_count = int(resonance["family_reverse_resonance"].sum()) if not resonance.empty else 0
    trend_frame = trend_signal_frame(resonance, trend_temperature)
    index_frame = stock_index_frame(index_resonance, trend_temperature)
    equity_sentiment = load_equity_sentiment_summary()

    css = """
    :root{--bg:#f4f6f8;--panel:#fff;--ink:#202630;--muted:#687281;--line:#dfe5eb;--strong:#111820;--gold:#b18438;--red:#c94c5a;--red2:#f8e0e3;--green:#087b68;--green2:#dff0eb;--soft:#f8f0dd;--blue:#426f9c}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;letter-spacing:0}.page{width:min(1240px,calc(100vw - 30px));margin:0 auto;padding:42px 0 54px}
    .top{display:grid;grid-template-columns:1fr auto;gap:26px;align-items:start;border-bottom:3px solid var(--strong);padding-bottom:24px}.eyebrow{font-size:12px;color:var(--gold);font-weight:900;text-transform:uppercase}.top h1{font-size:43px;line-height:1.04;margin:8px 0 8px}.sub{color:var(--muted);font-size:15px;line-height:1.65}.date{text-align:right}.date b{font-size:28px}.legend{display:flex;gap:12px;justify-content:flex-end;margin-top:12px;color:var(--muted);font-size:12px}.dot{width:9px;height:9px;border-radius:99px;display:inline-block}.dot.red,.rank-track i.red{background:var(--red)}.dot.green,.rank-track i.green{background:var(--green)}.dot.gold{background:var(--gold)}
    .section{margin-top:34px}.section-title{display:grid;grid-template-columns:42px 1fr auto;align-items:end;gap:16px;border-bottom:2px solid var(--strong);padding-bottom:10px;margin-bottom:16px}.section-title>*{min-width:0}.section-title em{font-style:normal;color:var(--gold);font-weight:900}.section-title h2{font-size:24px;margin:0}.section-title span{color:var(--muted);font-size:12px;overflow-wrap:anywhere}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:var(--panel);border-top:4px solid var(--strong);padding:20px;min-height:132px}.card.accent{background:var(--soft);border-top-color:var(--gold)}.card.domestic{border-top-color:#26384c}.card.foreign{border-top-color:#5a427c}.k{font-size:13px;color:var(--muted);font-weight:800}.v{font-size:34px;line-height:1.1;margin-top:12px;font-weight:900}.s{font-size:12px;color:var(--muted);margin-top:8px;line-height:1.6}.red,.bull{color:var(--red)}.green,.bear{color:var(--green)}.flat{color:var(--muted)}
    .rank-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.rank-list{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.sector-label{grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--strong);padding-top:9px;margin-top:5px;font-size:13px;font-weight:900}.sector-label span{font-size:11px;color:var(--muted);font-weight:700}.rank-card{background:#fff;border:1px solid var(--line);padding:14px}.sector-empty{grid-column:1/-1;background:#f7f9fa;border-style:dashed}.rank-head{display:flex;align-items:baseline;justify-content:space-between}.rank-head b{font-size:17px}.rank-head span,td span{display:block;color:var(--muted);font-size:11px;margin-top:2px}.rank-value{font-size:25px;font-weight:900;margin-top:8px}.rank-track{height:8px;background:#eef2f5;border-radius:99px;overflow:hidden;margin-top:9px}.rank-track i{height:100%;display:block;border-radius:99px}.rank-sub{font-size:11px;color:var(--muted);margin-top:8px}.rank-block h3{margin:0 0 10px;font-size:18px}.empty,.muted-text{color:var(--muted);font-size:13px}
    .table-scroll{max-width:100%;overflow-x:auto}table{width:100%;border-collapse:collapse;background:#fff}th{font-size:12px;text-align:left;color:#4d5663;background:#eef2f5;border-bottom:1px solid var(--line);padding:10px}td{border-bottom:1px solid #edf0f3;padding:11px 10px;vertical-align:middle}.sector-row td{background:#f7f2e7;border-top:2px solid #d6b577;color:#233041;padding:9px 10px}.sector-row b{font-size:14px}.sector-row span{display:inline;margin-left:12px;color:var(--muted);font-size:12px}.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:780}.stack{height:12px;background:#edf1f4;border-radius:99px;display:flex;overflow:hidden;min-width:152px}.stack span{height:100%;display:block}.stack .long{background:var(--red)}.stack .short{background:var(--green)}.stack.muted span:first-child{background:#d9dee5}.stack.muted span:last-child{background:#c8ced6}.pill{display:inline-block;border-radius:99px;padding:4px 9px;font-size:12px;font-weight:900;white-space:nowrap}.pill.bull{background:var(--red2);color:var(--red)}.pill.bear{background:var(--green2);color:var(--green)}.pill.flat{background:#edf1f4;color:var(--muted)}.pill.gold{background:#f6ecd8;color:#9b6a1f}.trend-temp{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:7px;font-weight:900;margin-right:6px}.trend-temp.bull{background:var(--red2);color:var(--red)}.trend-temp.bear{background:var(--green2);color:var(--green)}.trend-temp.flat{background:#edf1f4;color:var(--muted)}
    .flowbar{height:8px;background:#edf1f4;border-radius:99px;overflow:hidden;min-width:120px}.flowbar i{display:block;height:100%;border-radius:99px}.flowbar .bull{background:var(--red)}.flowbar .bear{background:var(--green)}.flowbar .flat{background:#b4bcc7}
    .signedbar{height:8px;background:#edf1f4;border-radius:99px;display:grid;grid-template-columns:1fr 1px 1fr;align-items:center;overflow:hidden;min-width:128px}.signedbar em{height:100%;background:#9ba6b3}.signedbar i{height:100%;display:block}.signedbar .neg{justify-self:end;background:var(--green);border-radius:99px 0 0 99px}.signedbar .pos{justify-self:start;background:var(--red);border-radius:0 99px 99px 0}.compare-cell{min-width:154px}.compare-meta{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-top:5px}.compare-meta b{font-variant-numeric:tabular-nums}.compare-meta span{font-size:10px;color:var(--muted);line-height:1.25}
    .broker-grid.domestic{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.broker-grid.foreign{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.broker-card{background:#fff;border:1px solid var(--line);padding:14px}.broker-card h3{margin:0 0 12px;font-size:18px}.broker-sector{border-top:1px solid var(--strong);padding-top:7px;margin-top:5px;color:var(--gold);font-size:12px;font-weight:900}.broker-sector span{display:block;color:var(--muted);font-size:10px;font-weight:700;line-height:1.45;margin-top:3px}.broker-row{display:grid;grid-template-columns:92px 1fr 86px;align-items:center;gap:10px;padding:7px 0;border-top:1px solid #eef1f4}.broker-meter{height:8px;background:#edf1f4;border-radius:99px;overflow:hidden}.broker-meter i{display:block;height:100%;border-radius:99px}.broker-meter i.bull{background:var(--red)}.broker-meter i.bear{background:var(--green)}.broker-meter i.flat{background:#b4bcc7}
    .status{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.status-row{background:#fff;border:1px solid var(--line);padding:10px;display:grid;grid-template-columns:1fr auto;gap:5px;align-items:center}.status-row b{font-size:14px}.status-row span,.status-row em{font-size:12px;color:var(--muted);font-style:normal}.status-row strong{font-size:12px}.status-row.warn{border-color:#e0b56f;background:#fff8e8}.note{background:#fff8e6;border-left:5px solid var(--gold);padding:16px 18px;line-height:1.7}.foot{font-size:11px;color:var(--muted);border-top:1px solid var(--line);margin-top:30px;padding-top:14px}
    .sentiment-grid{display:grid;grid-template-columns:230px 1fr 1.2fr;gap:12px;margin-top:14px}.sentiment-score,.sentiment-copy{background:#fff;border:1px solid var(--line);padding:18px}.sentiment-score{border-top:4px solid var(--gold)}.sentiment-score .v{font-variant-numeric:tabular-nums}.sentiment-label{font-size:20px;font-weight:900;margin-top:4px}.sentiment-copy h3{font-size:14px;margin:0 0 8px}.sentiment-copy h3:not(:first-child){margin-top:16px}.sentiment-copy p{font-size:13px;line-height:1.75;color:#394351;margin:0}.sentiment-copy ul{list-style:none;padding:0;margin:0}.sentiment-copy li{font-size:12px;line-height:1.65;padding:7px 0;border-top:1px solid #edf0f3}.sentiment-copy li:first-child{border-top:0}.sentiment-copy li .pill{margin-right:8px}.hint{color:var(--muted)!important;margin-top:12px!important}
    @media(max-width:920px){.top,.cards,.rank-grid,.broker-grid.domestic,.broker-grid.foreign,.status,.sentiment-grid{grid-template-columns:1fr}.date{text-align:left}.legend{justify-content:flex-start}.rank-list{grid-template-columns:1fr}.section-title{grid-template-columns:1fr}.top h1{font-size:34px}}
    """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<link rel="icon" href="data:," />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>保证金金额口径席位日报 {html.escape(str(date_label))}</title>
<style>{css}</style>
</head>
<body>
<main class="page">
  <header class="top">
    <div>
      <div class="eyebrow">Margin Weighted Positioning · Daily Flow Atlas</div>
      <h1>保证金金额口径席位日报</h1>
      <div class="sub">用“方向变化手数 × 当前一手交易保证金”重算每日席位资金变化；加多/减空计偏多，减多/加空计偏空，同时保留多头边际与空头边际的结构判断。</div>
    </div>
    <div class="date">
      <b>{html.escape(str(date_label))}</b>
      <div class="sub">席位来源：奇货可查 broker/position<br/>保证金来源：东方财富期货保证金表，{html.escape(margin_update or '-')}<br/>覆盖品种：{coverage_text}</div>
      <div class="legend"><span><i class="dot red"></i> 看多/加多</span><span><i class="dot green"></i> 看空/加空</span><span><i class="dot gold"></i> 共振</span></div>
    </div>
  </header>

  <section class="section">
    <div class="section-title"><em>01</em><h2>金额口径摘要</h2><span>单位：亿元；方向金额 = 加多金额 + 减空金额 - 减多金额 - 加空金额</span></div>
    <div class="cards">
      <div class="card"><div class="k">机构合计金额方向</div><div class="v {direction_class(institutional_score)}">{money_yi(institutional_score)}</div><div class="s">内资 + 外资；当前为 {direction(institutional_score)}。家人反向金额为 {money_yi(family_reverse_score)}。</div></div>
      {group_card(domestic, "内资机构", "domestic")}
      {group_card(foreign, "外资席位", "foreign")}
      <div class="card accent"><div class="k">三方强共振</div><div class="v">{triple_count} 个</div><div class="s">内外资同向且家人反向后同向；偏多 {triple_bull_count}，偏空 {triple_bear_count}。</div></div>
    </div>
  </section>

  <section class="section">
    <div class="section-title"><em>02</em><h2>三方共振净金额排行</h2><span>按商品板块分别列出前三净多、前三净空；计算口径 = 内资 + 外资 - 家人席位</span></div>
    <div class="rank-grid">
      <div class="rank-block"><h3>三方共振净偏多金额</h3><div class="rank-list">{institutional_net_cards(resonance, "bull")}</div></div>
      <div class="rank-block"><h3>三方共振净偏空金额</h3><div class="rank-list">{institutional_net_cards(resonance, "bear")}</div></div>
    </div>
  </section>

  <section class="section">
    <div class="section-title"><em>03</em><h2>趋势温度与资金共振</h2><span>趋势动物 API 直接事实与三方资金判断分列展示；温/热/沸为多头趋势，凉/寒/冻为空头趋势；平指标过滤</span></div>
    <div class="cards">{trend_summary_cards(trend_frame, trend_status)}</div>
    <div class="table-scroll"><table style="margin-top:14px">
      <thead><tr><th>品种</th><th>趋势温度</th><th>右侧/天数</th><th>阶段/温度变化</th><th class="num">局部强度</th><th class="num">日收益原值</th><th>资金关系</th><th>三方净金额</th><th class="num">机构合计</th><th class="num">家人反向</th><th>资金共振</th></tr></thead>
      <tbody>{trend_temperature_rows(trend_frame, 26)}</tbody>
    </table></div>
  </section>

  <section class="section">
    <div class="section-title"><em>04</em><h2>股指资金与趋势观察</h2><span>本板块独立于商品统计；四个股指期货展示三方净保证金变化，科创50/创业板50仅在趋势 API 可检索时展示</span></div>
    <div class="table-scroll"><table>
      <thead><tr><th>指数</th><th>三方净资金流</th><th class="num">机构合计</th><th class="num">家人反向</th><th>趋势温度</th><th class="num">当日涨跌</th><th>资金 / 趋势</th><th>数据日</th></tr></thead>
      <tbody>{stock_index_rows(index_frame)}</tbody>
    </table></div>
    <div class="analysis-box"><p class="hint">三方净资金流 = 内资 + 外资 - 家人席位。Trend Animal 官方文档未明确 return1d 的展示单位，因此当日涨跌保留接口原值，不擅自换算为百分比。</p></div>
    {equity_sentiment_panel(equity_sentiment)}
  </section>

  <section class="section">
    <div class="section-title"><em>05</em><h2>期货资金潮汐</h2><span>当前底表暂无行情涨跌字段，先以资金净流入/流出 × 总持仓增/减判断边际状态</span></div>
    <div class="table-scroll"><table>
      <thead><tr><th>品种</th><th>潮汐状态</th><th>资金净流</th><th>总持仓变化</th><th class="num">内资净额</th><th class="num">外资净额</th><th class="num">家人原始净额</th></tr></thead>
      <tbody>{amount_tide_rows(resonance, 20)}</tbody>
    </table></div>
  </section>

  <section class="section">
    <div class="section-title"><em>06</em><h2>金额边际结构矩阵</h2><span>内资、外资、家人均为净金额变动；最后一列为内资 + 外资 + 家人原始方向的三方净变动</span></div>
    <div class="table-scroll"><table>
      <thead><tr><th>品种</th><th>信号</th><th class="num">一手保证金</th><th class="num">内资净额</th><th class="num">外资净额</th><th class="num">家人原始净额</th><th class="num">家人反向净额</th><th>机构边际结构</th><th>强度</th><th class="num">三方净变动</th></tr></thead>
      <tbody>{amount_rows(resonance, 26)}</tbody>
    </table></div>
  </section>

  <section class="section">
    <div class="section-title"><em>07</em><h2>机构与家人反向共振</h2><span>内资、外资、家人均为净金额变动；最后一列为内资 + 外资 + 家人原始方向的三方净变动</span></div>
    <div class="table-scroll"><table>
      <thead><tr><th>品种</th><th>共振类型</th><th class="num">内资净额</th><th class="num">外资净额</th><th class="num">机构合计净额</th><th class="num">家人原始净额</th><th class="num">家人反向净额</th><th class="num">三方净变动</th></tr></thead>
      <tbody>{resonance_rows(resonance, 20)}</tbody>
    </table></div>
  </section>

  <section class="section">
    <div class="section-title"><em>08</em><h2>内资席位净金额分拆</h2><span>每家内资席位按品种净金额变动排序</span></div>
    <div class="broker-grid domestic">{''.join(broker_panel(broker_summary, broker) for broker in DOMESTIC_BROKERS)}</div>
  </section>

  <section class="section">
    <div class="section-title"><em>09</em><h2>外资席位净金额分拆</h2><span>三家外资席位按品种净金额变动排序</span></div>
    <div class="broker-grid foreign">{''.join(broker_panel(broker_summary, broker) for broker in FOREIGN_BROKERS)}</div>
  </section>

  <section class="section">
    <div class="section-title"><em>10</em><h2>抓取与保证金状态</h2><span>席位复用/抓取来源：{html.escape(position_source)}；缺失保证金：{html.escape(', '.join(missing_symbols) if missing_symbols else '无')}</span></div>
    <div class="status">{status_cards(fetch_status)}</div>
  </section>

  <section class="section note">
    <b>金额口径说明：</b>保证金表按周缓存，默认 7 天内复用同一份东方财富期货保证金表；需要强制刷新时设置 <code>FORCE_MARGIN_REFRESH=1</code>。本报告将同一品种所有席位合约的变化手数乘以当前缓存的一手保证金，用于横向比较资金量级；它不是投资者账户的实际占用保证金，也不是逐远月合约逐笔精确保证金。若某品种保证金缺失，则金额列按 0 处理并在状态区标注。  </section>

  <div class="foot">本报告仅为席位持仓与保证金数据整理，不构成投资建议。生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}。</div>
</main>
</body>
</html>"""


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    margin_ref, margin_status = fetch_margin_reference()
    trend_temperature, trend_status = load_trend_temperature()
    raw_rows, fetch_status, position_source = fetch_position_rows()
    raw_symbols = raw_rows.get("symbol", pd.Series(dtype=str)).astype(str).str.upper()
    index_rows = raw_rows[raw_symbols.isin(INDEX_FUTURE_SYMBOLS)].copy()
    rows = BASE.filter_commodity_rows(raw_rows)
    rows = add_flow_and_amounts(rows, margin_ref)
    index_rows = add_flow_and_amounts(index_rows, margin_ref)

    domestic = summarize_group(rows, "内资")
    foreign = summarize_group(rows, "外资")
    family = summarize_group(rows, "家人")
    broker_summary = summarize_broker(rows)
    resonance = build_resonance(domestic, foreign, family)

    index_domestic = summarize_group(index_rows, "内资")
    index_foreign = summarize_group(index_rows, "外资")
    index_family = summarize_group(index_rows, "家人")
    index_resonance = build_resonance(index_domestic, index_foreign, index_family)
    if not index_resonance.empty:
        index_resonance["variety"] = index_resonance["symbol"].map(INDEX_NAMES).fillna(index_resonance["variety"])

    rows.to_csv(DATA_DIR / "amount_contract_rows.csv", index=False, encoding="utf-8-sig")
    fetch_status.to_csv(DATA_DIR / "fetch_status.csv", index=False, encoding="utf-8-sig")
    margin_ref.to_csv(DATA_DIR / "margin_reference.csv", index=False, encoding="utf-8-sig")
    margin_status.to_csv(DATA_DIR / "margin_fetch_status.csv", index=False, encoding="utf-8-sig")
    trend_temperature.to_csv(DATA_DIR / "trend_temperature_used.csv", index=False, encoding="utf-8-sig")
    domestic.to_csv(DATA_DIR / "domestic_amount_summary.csv", index=False, encoding="utf-8-sig")
    foreign.to_csv(DATA_DIR / "foreign_amount_summary.csv", index=False, encoding="utf-8-sig")
    family.to_csv(DATA_DIR / "family_amount_summary.csv", index=False, encoding="utf-8-sig")
    broker_summary.to_csv(DATA_DIR / "broker_amount_summary.csv", index=False, encoding="utf-8-sig")
    resonance.to_csv(DATA_DIR / "institutional_amount_resonance.csv", index=False, encoding="utf-8-sig")
    index_rows.to_csv(DATA_DIR / "stock_index_amount_contract_rows.csv", index=False, encoding="utf-8-sig")
    index_resonance.to_csv(DATA_DIR / "stock_index_amount_resonance.csv", index=False, encoding="utf-8-sig")

    html_text = build_html(rows, fetch_status, margin_status, trend_temperature, trend_status, domestic, foreign, family, broker_summary, resonance, index_resonance, position_source)
    (OUT_DIR / "report.html").write_text(html_text, encoding="utf-8")

    used_symbols = rows["symbol"].nunique() if not rows.empty else 0
    matched_symbols = rows.loc[~rows["margin_missing"], "symbol"].nunique() if not rows.empty else 0
    print(f"report: {OUT_DIR / 'report.html'}")
    print(f"rows: {len(rows)}")
    print(f"margin coverage: {matched_symbols}/{used_symbols}")
    print(f"triple resonance: {int(resonance['triple_resonance'].sum()) if not resonance.empty else 0}")
    print(f"domestic+foreign same: {int(resonance['domestic_foreign_same'].sum()) if not resonance.empty else 0}")


if __name__ == "__main__":
    main()
