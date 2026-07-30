from __future__ import annotations

import html
import importlib.util
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from fetch_qhk_weather_risk import fetch_weather_risk


ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
SKIP_REPORT_HTML = os.environ.get("SKIP_REPORT_HTML", "").strip().lower() in {"1", "true", "yes"}
OUT_DIR = ROOT / "output" / f"institutional_seat_report_{RUN_DATE}"
DATA_DIR = OUT_DIR / "data"

DOMESTIC_BROKERS = ["国泰君安", "东证期货", "永安期货", "海通期货", "浙商期货", "中财期货", "南华期货", "申银万国", "中信期货", "光大期货", "一德期货", "瑞达期货", "银河期货"]
FOREIGN_BROKERS = ["高盛期货", "摩根大通", "瑞银期货"]
FAMILY_BROKERS = ["东方财富", "徽商期货", "方正中期", "华安期货", "中信建投", "广发期货", "民生期货", "平安期货", "中泰期货"]

GROUPS = {
    "内资": DOMESTIC_BROKERS,
    "外资": FOREIGN_BROKERS,
    "家人": FAMILY_BROKERS,
}


def load_base_module():
    spec = importlib.util.spec_from_file_location("futures_report_base", ROOT / "scripts" / "generate_futures_report.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/generate_futures_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base_module()


def signed(value: float | int) -> str:
    return f"{int(value):+,}"


def unsigned(value: float | int) -> str:
    return f"{int(value):,}"


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


def sign(value: float | int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


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


def sector_sort(df: pd.DataFrame, score_col: str, ascending: bool = False) -> pd.DataFrame:
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


def fetch_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    status: list[dict] = []
    requested_date = f"{RUN_DATE[:4]}-{RUN_DATE[4:6]}-{RUN_DATE[6:]}"
    for group, brokers in GROUPS.items():
        for broker in brokers:
            try:
                date, url, broker_rows = BASE.fetch_broker(broker, requested_date)
                if date and date > requested_date:
                    raise RuntimeError(
                        f"席位披露日期 {date} 晚于报告日 {requested_date}"
                    )
                status.append({"group": group, "broker": broker, "date": date, "rows": len(broker_rows), "url": url, "note": "OK"})
                for row in broker_rows:
                    item = dict(row)
                    item["group"] = group
                    rows.append(item)
            except Exception as exc:
                status.append({"group": group, "broker": broker, "date": "", "rows": 0, "url": "", "note": f"ERROR: {exc}"})
    return pd.DataFrame(rows), pd.DataFrame(status)


def add_flow_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["add_long"] = df["long_chg"].clip(lower=0)
    df["reduce_long"] = (-df["long_chg"]).clip(lower=0)
    df["add_short"] = df["short_chg"].clip(lower=0)
    df["reduce_short"] = (-df["short_chg"]).clip(lower=0)
    df["bull_flow"] = df["add_long"] + df["reduce_short"]
    df["bear_flow"] = df["reduce_long"] + df["add_short"]
    df["flow_score"] = df["bull_flow"] - df["bear_flow"]
    df["gross_pos"] = df["long_pos"] + df["short_pos"]
    df["net_pos"] = df["long_pos"] - df["short_pos"]
    df["activity"] = df["add_long"] + df["reduce_long"] + df["add_short"] + df["reduce_short"]
    return df


SUMMARY_COLS = [
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
    "activity",
    "add_activity",
    "rows",
    "min_date",
    "max_date",
]


def empty_summary() -> pd.DataFrame:
    return pd.DataFrame(columns=SUMMARY_COLS)


def summarize_group(df: pd.DataFrame, group: str) -> pd.DataFrame:
    if df.empty:
        return empty_summary()
    group_df = df[df["group"] == group]
    if group_df.empty:
        return empty_summary()
    grouped = group_df.groupby(["variety", "symbol"], as_index=False).agg(
        add_long=("add_long", "sum"),
        reduce_long=("reduce_long", "sum"),
        add_short=("add_short", "sum"),
        reduce_short=("reduce_short", "sum"),
        bull_flow=("bull_flow", "sum"),
        bear_flow=("bear_flow", "sum"),
        flow_score=("flow_score", "sum"),
        long_chg=("long_chg", "sum"),
        short_chg=("short_chg", "sum"),
        long_pos=("long_pos", "sum"),
        short_pos=("short_pos", "sum"),
        net_pos=("net_pos", "sum"),
        gross_pos=("gross_pos", "sum"),
        rows=("contract", "count"),
        min_date=("date", "min"),
        max_date=("date", "max"),
    )
    grouped["activity"] = grouped["add_long"] + grouped["reduce_long"] + grouped["add_short"] + grouped["reduce_short"]
    grouped["add_activity"] = grouped["add_long"] + grouped["add_short"]
    grouped["dir"] = grouped["flow_score"].map(direction)
    return grouped.sort_values("activity", ascending=False)


def summarize_broker(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = df[df["group"].isin(["内资", "外资"])].groupby(["group", "broker", "variety", "symbol"], as_index=False).agg(
        add_long=("add_long", "sum"),
        add_short=("add_short", "sum"),
        reduce_long=("reduce_long", "sum"),
        reduce_short=("reduce_short", "sum"),
        flow_score=("flow_score", "sum"),
    )
    grouped["activity"] = grouped["add_long"] + grouped["add_short"] + grouped["reduce_long"] + grouped["reduce_short"]
    grouped["dir"] = grouped["flow_score"].map(direction)
    return grouped.sort_values(["group", "broker", "activity"], ascending=[True, True, False])


def prefix_summary(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["variety", "symbol"])
    keep = [c for c in SUMMARY_COLS if c in df.columns]
    renamed = {c: f"{prefix}_{c}" for c in keep if c not in ["variety", "symbol"]}
    return df[keep].rename(columns=renamed)


def build_resonance(domestic: pd.DataFrame, foreign: pd.DataFrame, family: pd.DataFrame) -> pd.DataFrame:
    merged = prefix_summary(domestic, "domestic").merge(prefix_summary(foreign, "foreign"), on=["variety", "symbol"], how="outer")
    merged = merged.merge(prefix_summary(family, "family"), on=["variety", "symbol"], how="outer")

    numeric_cols = [c for c in merged.columns if c not in ["variety", "symbol"] and not c.endswith("_date")]
    for col in numeric_cols:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
    for col in [c for c in merged.columns if c.endswith("_date")]:
        merged[col] = merged[col].fillna("")

    for prefix in ["domestic", "foreign", "family"]:
        for col in ["flow_score", "add_long", "add_short", "reduce_long", "reduce_short", "activity", "add_activity"]:
            name = f"{prefix}_{col}"
            if name not in merged.columns:
                merged[name] = 0

    merged["institutional_score"] = merged["domestic_flow_score"] + merged["foreign_flow_score"]
    merged["family_reverse_score"] = -merged["family_flow_score"]
    merged["combined_signal"] = merged["institutional_score"] + merged["family_reverse_score"]
    merged["raw_three_group_score"] = merged["institutional_score"] + merged["family_flow_score"]
    merged["all_long_chg"] = merged["domestic_long_chg"] + merged["foreign_long_chg"] + merged["family_long_chg"]
    merged["all_short_chg"] = merged["domestic_short_chg"] + merged["foreign_short_chg"] + merged["family_short_chg"]
    merged["all_position_chg"] = merged["all_long_chg"] + merged["all_short_chg"]
    merged["total_activity"] = merged["domestic_activity"] + merged["foreign_activity"] + merged["family_activity"]

    def classify(row: pd.Series) -> pd.Series:
        domestic_sign = sign(row["domestic_flow_score"])
        foreign_sign = sign(row["foreign_flow_score"])
        institutional_sign = sign(row["institutional_score"])
        family_reverse_sign = sign(row["family_reverse_score"])
        inner_same = domestic_sign != 0 and domestic_sign == foreign_sign
        family_reverse = institutional_sign != 0 and family_reverse_sign != 0 and institutional_sign == family_reverse_sign
        triple = inner_same and family_reverse and domestic_sign == family_reverse_sign
        if triple:
            label = "三方偏多共振" if family_reverse_sign > 0 else "三方偏空共振"
            strength = min(abs(row["domestic_flow_score"]), abs(row["foreign_flow_score"]), abs(row["family_reverse_score"]))
        elif inner_same:
            label = "内外资偏多共振" if domestic_sign > 0 else "内外资偏空共振"
            strength = min(abs(row["domestic_flow_score"]), abs(row["foreign_flow_score"]))
        elif family_reverse:
            label = "机构与家人反向"
            strength = min(abs(row["institutional_score"]), abs(row["family_reverse_score"]))
        else:
            label = "分歧"
            strength = max(abs(row["domestic_flow_score"]), abs(row["foreign_flow_score"]), abs(row["family_reverse_score"]))
        return pd.Series(
            {
                "domestic_foreign_same": inner_same,
                "family_reverse_resonance": family_reverse,
                "triple_resonance": triple,
                "resonance_label": label,
                "resonance_strength": strength,
                "signal_dir": direction(row["combined_signal"] if row["combined_signal"] else row["institutional_score"]),
            }
        )

    labels = merged.apply(classify, axis=1)
    merged = pd.concat([merged, labels], axis=1)
    merged = BASE.add_sector_columns(merged)
    return merged.sort_values(["triple_resonance", "family_reverse_resonance", "resonance_strength", "total_activity"], ascending=[False, False, False, False])


def bar_pair(add_long: float, add_short: float) -> str:
    total = add_long + add_short
    if total <= 0:
        return '<div class="stack muted"><span style="width:50%"></span><span style="width:50%"></span></div>'
    long_pct = round(add_long / total * 100) if add_long else 0
    short_pct = 100 - long_pct if add_short else 0
    if add_long and not add_short:
        long_pct, short_pct = 100, 0
    if add_short and not add_long:
        long_pct, short_pct = 0, 100
    if add_long:
        long_pct = max(3, long_pct)
    if add_short:
        short_pct = max(3, short_pct)
    return f"""
    <div class="stack" title="加多 {unsigned(add_long)} / 加空 {unsigned(add_short)}">
      <span class="long" style="width:{long_pct}%"></span>
      <span class="short" style="width:{short_pct}%"></span>
    </div>
    """


def mini_flow_bar(value: float, max_abs: float) -> str:
    if max_abs <= 0:
        max_abs = 1
    width = max(2, min(100, abs(value) / max_abs * 100)) if value else 0
    return f'<div class="flowbar"><i class="{direction_class(value)}" style="width:{width:.1f}%"></i></div>'


def signed_bar(value: float, max_abs: float) -> str:
    max_abs = max(max_abs, 1)
    width = max(2, min(100, abs(value) / max_abs * 100)) if value else 0
    return f"""
    <div class="signedbar">
      <span class="zero"></span>
      <i class="{direction_class(value)}" style="width:{width:.1f}%"></i>
    </div>
    """


def tide_bucket(flow: float, position_chg: float) -> str:
    flow_label = "资金流入" if flow > 0 else "资金流出" if flow < 0 else "资金平衡"
    pos_label = "增仓" if position_chg > 0 else "减仓" if position_chg < 0 else "持仓平"
    return f"{flow_label} · {pos_label}"


def tide_rows(resonance: pd.DataFrame, limit: int = 20) -> str:
    if resonance.empty:
        return '<tr><td colspan="7" class="muted-text">无可用潮汐数据</td></tr>'
    selected = resonance.assign(
        tide_strength=lambda x: x["raw_three_group_score"].abs() + x["all_position_chg"].abs() * 0.35
    ).sort_values("tide_strength", ascending=False).head(limit)
    selected = sector_sort(selected, "tide_strength")
    max_flow = max(selected["raw_three_group_score"].abs().max(), 1)
    max_pos = max(selected["all_position_chg"].abs().max(), 1)
    rows = []
    current_sector = None
    for _, r in selected.iterrows():
        if r["sector"] != current_sector:
            current_sector = r["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            rows.append(sector_header(current_sector, 7, sector_direction_text(sector_part, "raw_three_group_score")))
        flow = r["raw_three_group_score"]
        pos_chg = r["all_position_chg"]
        rows.append(
            f"""
            <tr>
              <td>{name_code(r['variety'], r['symbol'])}</td>
              <td><span class="pill {direction_class(flow)}">{html.escape(tide_bucket(flow, pos_chg))}</span></td>
              <td>{signed_bar(flow, max_flow)}<span class="{direction_class(flow)}">净流 {signed(flow)}</span></td>
              <td>{signed_bar(pos_chg, max_pos)}<span class="{direction_class(pos_chg)}">持仓 {signed(pos_chg)}</span></td>
              <td class="num {direction_class(r['domestic_flow_score'])}">{signed(r['domestic_flow_score'])}</td>
              <td class="num {direction_class(r['foreign_flow_score'])}">{signed(r['foreign_flow_score'])}</td>
              <td class="num {direction_class(r['family_flow_score'])}">{signed(r['family_flow_score'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def group_compare_cell(row: pd.Series, prefix: str, max_abs: float) -> str:
    score = row.get(f"{prefix}_flow_score", 0)
    long_chg = row.get(f"{prefix}_long_chg", 0)
    short_chg = row.get(f"{prefix}_short_chg", 0)
    pos_chg = long_chg + short_chg
    return f"""
    <div class="compare-cell">
      {signed_bar(score, max_abs)}
      <div class="compare-meta">
        <b class="{direction_class(score)}">{signed(score)}</b>
        <span>多 {signed(long_chg)} / 空 {signed(short_chg)} / 持仓 {signed(pos_chg)}</span>
      </div>
    </div>
    """


def current_position_cell(row: pd.Series, max_abs: float) -> str:
    institutional = row.get("domestic_net_pos", 0) + row.get("foreign_net_pos", 0)
    family = row.get("family_net_pos", 0)
    return f"""
    <div class="compare-cell position-cell">
      {signed_bar(institutional, max_abs)}
      <div class="compare-meta"><b class="{direction_class(institutional)}">机构 {signed(institutional)}</b></div>
      {signed_bar(family, max_abs)}
      <div class="compare-meta"><span class="{direction_class(family)}">家人原始 {signed(family)}</span></div>
    </div>
    """


def net_cards(resonance: pd.DataFrame, side: str, label: str, per_sector: int = 3) -> str:
    if resonance.empty:
        return '<div class="empty">无可用数据</div>'
    working = BASE.add_sector_columns(resonance)
    score_col = "combined_signal"
    if side == "bull":
        side_text = "净多"
        missing_text = "今天没有净多品种"
        selector = lambda part: part[part[score_col] > 0].sort_values(score_col, ascending=False).head(per_sector)
    else:
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
            cls = "red" if score > 0 else "green"
            cards.append(
                f"""
                <div class="rank-card">
                  <div class="rank-head">{name_code(row['variety'], row['symbol'])}</div>
                  <div class="rank-value {cls}">{signed(score)}</div>
                  <div class="rank-track"><i class="{cls}" style="width:{width:.1f}%"></i></div>
                  <div class="rank-sub">{html.escape(label)}；板块{side_text}前{per_sector} / 机构 {signed(row['institutional_score'])}，家人反向 {signed(row['family_reverse_score'])}</div>
                </div>
                """
            )
    return "\n".join(cards)


def relation_note(row: pd.Series, base_score: float) -> str:
    score_sign = sign(base_score)
    foreign_score = row.get("foreign_flow_score", 0)
    family_reverse_score = row.get("family_reverse_score", 0)
    parts = []
    if sign(foreign_score) == score_sign:
        parts.append(f"外资同向{direction(foreign_score)}")
    elif sign(foreign_score) == 0:
        parts.append("外资无明显覆盖")
    else:
        parts.append(f"外资反向{direction(foreign_score)}")
    if sign(family_reverse_score) == score_sign:
        parts.append(f"家人反向后同向{direction(family_reverse_score)}")
    elif sign(family_reverse_score) == 0:
        parts.append("家人无明显反向验证")
    else:
        parts.append(f"家人反向后对冲{direction(family_reverse_score)}")
    label = str(row.get("resonance_label", ""))
    if label:
        parts.append(label)
    return "；".join(parts)


def divergence_rows(domestic: pd.DataFrame, resonance: pd.DataFrame, limit: int = 10) -> str:
    if domestic.empty:
        return '<tr><td colspan="7" class="muted-text">无可用数据</td></tr>'
    columns = ["variety", "symbol", "foreign_flow_score", "family_flow_score", "family_reverse_score", "resonance_label"]
    available = [col for col in columns if col in resonance.columns]
    merged = domestic.merge(resonance[available], on=["variety", "symbol"], how="left") if available else domestic.copy()
    for col in ["foreign_flow_score", "family_flow_score", "family_reverse_score"]:
        if col not in merged.columns:
            merged[col] = 0
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
    rows = []
    for _, r in merged.iterrows():
        score = r["flow_score"]
        if score > 0:
            counter = r["reduce_long"] + r["add_short"]
            if counter <= 0:
                continue
            counter_text = f"减多 {unsigned(r['reduce_long'])} / 加空 {unsigned(r['add_short'])}"
        elif score < 0:
            counter = r["add_long"] + r["reduce_short"]
            if counter <= 0:
                continue
            counter_text = f"加多 {unsigned(r['add_long'])} / 减空 {unsigned(r['reduce_short'])}"
        else:
            continue
        activity = max(float(r.get("activity", 0)), 1)
        if counter / activity < 0.18:
            continue
        rows.append((counter, r))
    if not rows:
        return '<tr><td colspan="7" class="muted-text">无显著背离项</td></tr>'
    rows = sorted(rows, key=lambda item: item[0], reverse=True)[:limit]
    selected = BASE.add_sector_columns(pd.DataFrame([dict(item[1]) for item in rows]))
    selected["_counter"] = [item[0] for item in rows]
    selected = sector_sort(selected, "_counter")
    html_rows = []
    current_sector = None
    for _, r in selected.iterrows():
        counter = r["_counter"]
        if r["sector"] != current_sector:
            current_sector = r["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            html_rows.append(sector_header(current_sector, 7, sector_direction_text(sector_part, "flow_score")))
        score = r["flow_score"]
        cls = direction_class(score)
        if score > 0:
            counter_text = f"减多 {unsigned(r['reduce_long'])} / 加空 {unsigned(r['add_short'])}"
        else:
            counter_text = f"加多 {unsigned(r['add_long'])} / 减空 {unsigned(r['reduce_short'])}"
        split_text = f"偏多 {unsigned(r['bull_flow'])} / 偏空 {unsigned(r['bear_flow'])}"
        html_rows.append(
            f"""
            <tr>
              <td>{name_code(r['variety'], r['symbol'])}</td>
              <td><span class="pill {cls}">{direction(score)}</span></td>
              <td class="num {cls}">{signed(score)}</td>
              <td>{html.escape(counter_text)}<span>{html.escape(split_text)}</span></td>
              <td class="num {direction_class(r['foreign_flow_score'])}">{signed(r['foreign_flow_score'])}</td>
              <td class="num {direction_class(r['family_reverse_score'])}">{signed(r['family_reverse_score'])}<span>原始 {signed(r['family_flow_score'])}</span></td>
              <td class="reason">{html.escape(relation_note(r, score))}</td>
            </tr>
            """
        )
    return "\n".join(html_rows)


def group_cards(summary: pd.DataFrame, label: str, css_class: str) -> str:
    if summary.empty:
        return f'<div class="card"><div class="k">{label}</div><div class="v">-</div><div class="s">无数据</div></div>'
    net = int(summary["flow_score"].sum())
    add_long = int(summary["add_long"].sum())
    add_short = int(summary["add_short"].sum())
    top = summary.sort_values("flow_score", ascending=net < 0).head(1)
    top_text = f"{top.iloc[0]['variety']} {signed(top.iloc[0]['flow_score'])}" if not top.empty else "-"
    return f"""
    <div class="card {css_class}">
      <div class="k">{html.escape(label)}</div>
      <div class="v {direction_class(net)}">{signed(net)}</div>
      <div class="s">加多 {unsigned(add_long)} / 加空 {unsigned(add_short)}；最强方向：{html.escape(top_text)}</div>
    </div>
    """


def progress_rows(resonance: pd.DataFrame, limit: int = 24) -> str:
    if resonance.empty:
        return '<tr><td colspan="9" class="muted-text">无可用数据</td></tr>'
    selected = resonance.sort_values(["triple_resonance", "resonance_strength", "total_activity"], ascending=[False, False, False]).head(limit)
    selected = sector_sort(selected, "total_activity")
    max_group = max(
        selected["domestic_flow_score"].abs().max(),
        selected["foreign_flow_score"].abs().max(),
        selected["family_flow_score"].abs().max(),
        selected["institutional_score"].abs().max(),
        1,
    )
    max_position = max(
        (selected["domestic_net_pos"] + selected["foreign_net_pos"]).abs().max(),
        selected["family_net_pos"].abs().max(),
        1,
    )
    selected["_sector_signal"] = selected.apply(lambda r: r["combined_signal"] if r["combined_signal"] else r["institutional_score"], axis=1)
    rows = []
    current_sector = None
    for _, r in selected.iterrows():
        if r["sector"] != current_sector:
            current_sector = r["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            rows.append(sector_header(current_sector, 9, sector_direction_text(sector_part, "_sector_signal")))
        signal_value = r["combined_signal"] if r["combined_signal"] else r["institutional_score"]
        rows.append(
            f"""
            <tr>
              <td>{name_code(r['variety'], r['symbol'])}</td>
              <td><span class="pill {direction_class(signal_value)}">{html.escape(str(r['resonance_label']))}</span></td>
              <td>{group_compare_cell(r, 'domestic', max_group)}</td>
              <td>{group_compare_cell(r, 'foreign', max_group)}</td>
              <td>{group_compare_cell(r, 'family', max_group)}</td>
              <td class="num {direction_class(r['family_reverse_score'])}">{signed(r['family_reverse_score'])}</td>
              <td>{signed_bar(r['institutional_score'], max_group)}<span class="{direction_class(r['institutional_score'])}">机构 {signed(r['institutional_score'])}</span></td>
              <td>{current_position_cell(r, max_position)}</td>
              <td class="num">{unsigned(r['total_activity'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def resonance_rows(resonance: pd.DataFrame, limit: int = 18) -> str:
    if resonance.empty:
        return '<tr><td colspan="8" class="muted-text">无可用数据</td></tr>'
    selected = resonance[(resonance["triple_resonance"]) | (resonance["family_reverse_resonance"])].head(limit)
    if selected.empty:
        return '<tr><td colspan="8" class="muted-text">暂无内外资同向且家人反向的强共振品种</td></tr>'
    selected["_sector_signal"] = selected.apply(lambda r: r["combined_signal"] if r["combined_signal"] else r["institutional_score"], axis=1)
    selected = sector_sort(selected, "resonance_strength")
    rows = []
    current_sector = None
    for _, r in selected.iterrows():
        if r["sector"] != current_sector:
            current_sector = r["sector"]
            sector_part = selected[selected["sector"] == current_sector]
            rows.append(sector_header(current_sector, 8, sector_direction_text(sector_part, "_sector_signal")))
        signal_value = r["combined_signal"] if r["combined_signal"] else r["institutional_score"]
        rows.append(
            f"""
            <tr>
              <td>{name_code(r['variety'], r['symbol'])}</td>
              <td><span class="pill {direction_class(signal_value)}">{html.escape(str(r['resonance_label']))}</span></td>
              <td class="num {direction_class(r['domestic_flow_score'])}">{signed(r['domestic_flow_score'])}</td>
              <td class="num {direction_class(r['foreign_flow_score'])}">{signed(r['foreign_flow_score'])}</td>
              <td class="num {direction_class(r['family_flow_score'])}">{signed(r['family_flow_score'])}</td>
              <td class="num {direction_class(r['family_reverse_score'])}">{signed(r['family_reverse_score'])}</td>
              <td class="num {direction_class(r['institutional_score'])}">{signed(r['institutional_score'])}</td>
              <td class="num">{unsigned(r['resonance_strength'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)



def broker_panel(broker_df: pd.DataFrame, broker: str) -> str:
    part = broker_df[broker_df["broker"] == broker].sort_values("activity", ascending=False).head(7)
    if part.empty:
        return f'<div class="broker-card"><h3>{html.escape(broker)}</h3><div class="empty">无数据</div></div>'
    part = sector_sort(part, "activity")
    max_activity = max(part["activity"].max(), 1)
    rows = []
    current_sector = None
    for _, r in part.iterrows():
        if r["sector"] != current_sector:
            current_sector = r["sector"]
            sector_part = part[part["sector"] == current_sector]
            rows.append(f'<div class="broker-sector">{html.escape(str(current_sector))}<span>{html.escape(sector_direction_text(sector_part, "flow_score"))}</span></div>')
        width = max(4, r["activity"] / max_activity * 100)
        cls = direction_class(r["flow_score"])
        rows.append(
            f"""
            <div class="broker-row">
              <div class="name-code">{name_code(r['variety'], r['symbol'])}</div>
              <div class="broker-meter"><i class="{cls}" style="width:{width:.1f}%"></i></div>
              <div class="num {cls}">{signed(r['flow_score'])}</div>
            </div>
            """
        )
    return f'<div class="broker-card"><h3>{html.escape(broker)}</h3>{"".join(rows)}</div>'


def status_cards(fetch_status: pd.DataFrame) -> str:
    cards = []
    for row in fetch_status.itertuples():
        note_cls = "ok" if row.note == "OK" and int(row.rows) > 0 else "warn"
        cards.append(
            f"""
            <div class="status-row {note_cls}">
              <b>{html.escape(str(row.broker))}</b>
              <span>{html.escape(str(row.group))}</span>
              <em>{html.escape(str(row.date or '-'))}</em>
              <strong>{int(row.rows)} 行</strong>
            </div>
            """
        )
    return "\n".join(cards)


def weather_risk_rows(weather: pd.DataFrame, resonance: pd.DataFrame) -> str:
    if weather.empty:
        return '<tr><td colspan="7" class="muted-text">天气预警暂不可用；席位资金结论不受影响。</td></tr>'

    funds = pd.DataFrame(columns=["symbol", "combined_signal"])
    if not resonance.empty and {"symbol", "combined_signal"}.issubset(resonance.columns):
        funds = resonance[["symbol", "combined_signal"]].copy()
    selected = weather.merge(funds, on="symbol", how="left")
    selected["combined_signal"] = pd.to_numeric(selected["combined_signal"], errors="coerce")

    level_names = {"high": "高", "medium": "中"}
    rows = []
    current_sector = None
    for _, row in selected.iterrows():
        if row["sector"] != current_sector:
            current_sector = row["sector"]
            rows.append(sector_header(current_sector, 7, "天气事实与三方席位资金分列，天气本身不代表涨跌方向"))
        score = row["combined_signal"]
        if pd.isna(score):
            fund_text = "席位未覆盖"
            fund_cls = "flat"
        else:
            fund_text = f"三方净{direction(score)} {signed(score)}"
            fund_cls = direction_class(score)
        risk_level = level_names.get(str(row.get("risk_level", "")), str(row.get("risk_level", "-")))
        rows.append(
            f"""
            <tr>
              <td><b>{html.escape(str(row['alert_window']))}</b><span>{html.escape(str(row['alert_date']))}</span></td>
              <td>{name_code(row['variety'], row['symbol'])}</td>
              <td><span class="pill {'bear' if risk_level == '高' else 'gold'}">{html.escape(risk_level)}风险</span><span>风险分 {float(row['risk_score']):.1f}</span></td>
              <td><b>{html.escape(str(row['risk_types']))}</b><span>{html.escape(str(row['origins']))}</span></td>
              <td class="reason">{html.escape(str(row['trigger_reason']))}</td>
              <td><b>{html.escape(str(row['market_reflection']))}</b><span>{html.escape(str(row['market_summary']))}</span></td>
              <td><span class="pill {fund_cls}">{html.escape(fund_text)}</span><span>仅作交叉验证，不把天气直接映射为多空。</span></td>
            </tr>
            """
        )
    return "\n".join(rows)


def build_html(
    rows: pd.DataFrame,
    fetch_status: pd.DataFrame,
    domestic: pd.DataFrame,
    foreign: pd.DataFrame,
    family: pd.DataFrame,
    broker_summary: pd.DataFrame,
    resonance: pd.DataFrame,
    weather: pd.DataFrame,
    weather_status: dict,
) -> str:
    dates = sorted(str(d) for d in fetch_status["date"].dropna().unique() if d)
    date_label = dates[-1] if dates else RUN_DATE
    total_rows = int(fetch_status["rows"].sum()) if not fetch_status.empty else 0
    institutional_score = int(domestic["flow_score"].sum() + foreign["flow_score"].sum()) if not domestic.empty or not foreign.empty else 0
    family_reverse_score = int(-family["flow_score"].sum()) if not family.empty else 0
    triple_count = int(resonance["triple_resonance"].sum()) if not resonance.empty else 0
    inner_same_count = int(resonance["domestic_foreign_same"].sum()) if not resonance.empty else 0
    family_reverse_count = int(resonance["family_reverse_resonance"].sum()) if not resonance.empty else 0
    triple_bull_count = int(((resonance["triple_resonance"]) & (resonance["combined_signal"] > 0)).sum()) if not resonance.empty else 0
    triple_bear_count = int(((resonance["triple_resonance"]) & (resonance["combined_signal"] < 0)).sum()) if not resonance.empty else 0

    css = """
    :root{--bg:#f4f6f8;--panel:#fff;--ink:#202630;--muted:#687281;--line:#dfe5eb;--strong:#111820;--gold:#b18438;--red:#c94c5a;--red2:#f8e0e3;--green:#087b68;--green2:#dff0eb;--blue:#426f9c;--blue2:#e5eef7;--soft:#f8f0dd}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;letter-spacing:0}.page{width:min(1240px,calc(100vw - 30px));margin:0 auto;padding:42px 0 54px}
    .top{display:grid;grid-template-columns:1fr auto;gap:26px;align-items:start;border-bottom:3px solid var(--strong);padding-bottom:24px}.eyebrow{font-size:12px;color:var(--gold);font-weight:900;text-transform:uppercase}.top h1{font-size:43px;line-height:1.04;margin:8px 0 8px}.sub{color:var(--muted);font-size:15px;line-height:1.65}.date{text-align:right}.date b{font-size:28px}.legend{display:flex;gap:12px;justify-content:flex-end;margin-top:12px;color:var(--muted);font-size:12px}.dot{width:9px;height:9px;border-radius:99px;display:inline-block}.dot.red,.rank-track i.red{background:var(--red)}.dot.green,.rank-track i.green{background:var(--green)}.dot.gold{background:var(--gold)}
    .section{margin-top:34px}.section-title{display:grid;grid-template-columns:42px 1fr auto;align-items:end;gap:16px;border-bottom:2px solid var(--strong);padding-bottom:10px;margin-bottom:16px}.section-title em{font-style:normal;color:var(--gold);font-weight:900}.section-title h2{font-size:24px;margin:0}.section-title span{color:var(--muted);font-size:12px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:var(--panel);border-top:4px solid var(--strong);padding:20px;min-height:132px}.card.accent{background:var(--soft);border-top-color:var(--gold)}.card.domestic{border-top-color:#26384c}.card.foreign{border-top-color:#5a427c}.k{font-size:13px;color:var(--muted);font-weight:800}.v{font-size:34px;line-height:1.1;margin-top:12px;font-weight:900}.s{font-size:12px;color:var(--muted);margin-top:8px;line-height:1.6}.red,.bull{color:var(--red)}.green,.bear{color:var(--green)}.flat{color:var(--muted)}
    .rank-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.rank-list{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.sector-label{grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--strong);padding-top:9px;margin-top:5px;font-size:13px;font-weight:900}.sector-label span{font-size:11px;color:var(--muted);font-weight:700}.rank-card{background:#fff;border:1px solid var(--line);padding:14px}.sector-empty{grid-column:1/-1;background:#f7f9fa;border-style:dashed}.rank-head{display:flex;align-items:baseline;justify-content:space-between}.rank-head b{font-size:17px}.rank-head span,td span,.name-code span{display:block;color:var(--muted);font-size:11px;margin-top:2px}.rank-value{font-size:25px;font-weight:900;margin-top:8px}.rank-track{height:8px;background:#eef2f5;border-radius:99px;overflow:hidden;margin-top:9px}.rank-track i{height:100%;display:block;border-radius:99px}.rank-sub{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.45}.rank-block h3{margin:0 0 10px;font-size:18px}.empty,.muted-text{color:var(--muted);font-size:13px}
    .analysis-box{background:#fff;border:1px solid var(--line);padding:14px;margin-top:18px}.analysis-box h3{margin:0 0 10px;font-size:18px}.analysis-box .hint{font-size:12px;color:var(--muted);margin:0 0 10px}.reason{font-size:12px;color:#495362;line-height:1.55}
    table{width:100%;border-collapse:collapse;background:#fff}th{font-size:12px;text-align:left;color:#4d5663;background:#eef2f5;border-bottom:1px solid var(--line);padding:10px}td{border-bottom:1px solid #edf0f3;padding:11px 10px;vertical-align:middle}.sector-row td{background:#f7f2e7;border-top:2px solid #d6b577;color:#233041;padding:9px 10px}.sector-row b{font-size:14px}.sector-row span{display:inline;margin-left:12px;color:var(--muted);font-size:12px}.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:780}.flow-cell{min-width:176px}.flow-cell span{font-size:12px;font-weight:850;margin-top:5px}.stack{height:12px;background:#edf1f4;border-radius:99px;display:flex;overflow:hidden;min-width:152px}.stack span{height:100%;display:block}.stack .long{background:var(--red)}.stack .short{background:var(--green)}.stack.muted span:first-child{background:#d9dee5}.stack.muted span:last-child{background:#c8ced6}.pill{display:inline-block;border-radius:99px;padding:4px 9px;font-size:12px;font-weight:900;white-space:nowrap}.pill.bull{background:var(--red2);color:var(--red)}.pill.bear{background:var(--green2);color:var(--green)}.pill.flat{background:#edf1f4;color:var(--muted)}
    .flowbar{height:8px;background:#edf1f4;border-radius:99px;overflow:hidden;min-width:120px}.flowbar i{display:block;height:100%;border-radius:99px}.flowbar .bull{background:var(--red)}.flowbar .bear{background:var(--green)}.flowbar .flat{background:#b4bcc7}
    .signedbar{position:relative;height:9px;background:#edf1f4;border-radius:99px;overflow:hidden;min-width:150px}.signedbar .zero{position:absolute;left:50%;top:0;bottom:0;width:1px;background:#aeb7c2}.signedbar i{position:absolute;top:0;height:100%;border-radius:99px}.signedbar i.bull{left:50%;background:var(--red)}.signedbar i.bear{right:50%;background:var(--green)}.signedbar i.flat{left:50%;background:#b4bcc7}.compare-cell{min-width:190px}.position-cell{min-width:160px}.compare-meta{display:grid;grid-template-columns:auto 1fr;gap:8px;align-items:center;margin-top:5px}.compare-meta b{font-variant-numeric:tabular-nums}.compare-meta span{font-size:11px;color:var(--muted);line-height:1.3}
    .broker-grid.domestic{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.broker-grid.foreign{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.broker-card{background:#fff;border:1px solid var(--line);padding:14px}.broker-card h3{margin:0 0 12px;font-size:18px}.broker-sector{border-top:1px solid var(--strong);padding-top:7px;margin-top:5px;color:var(--gold);font-size:12px;font-weight:900}.broker-sector span{display:block;color:var(--muted);font-size:10px;font-weight:700;line-height:1.45;margin-top:3px}.broker-row{display:grid;grid-template-columns:92px 1fr 74px;align-items:center;gap:10px;padding:7px 0;border-top:1px solid #eef1f4}.broker-meter{height:8px;background:#edf1f4;border-radius:99px;overflow:hidden}.broker-meter i{display:block;height:100%;border-radius:99px}.broker-meter i.bull{background:var(--red)}.broker-meter i.bear{background:var(--green)}.broker-meter i.flat{background:#b4bcc7}
    .status{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.status-row{background:#fff;border:1px solid var(--line);padding:10px;display:grid;grid-template-columns:1fr auto;gap:5px;align-items:center}.status-row b{font-size:14px}.status-row span,.status-row em{font-size:12px;color:var(--muted);font-style:normal}.status-row strong{font-size:12px}.status-row.warn{border-color:#e0b56f;background:#fff8e8}.note{background:#fff8e6;border-left:5px solid var(--gold);padding:16px 18px;line-height:1.7}.foot{font-size:11px;color:var(--muted);border-top:1px solid var(--line);margin-top:30px;padding-top:14px}
    @media(max-width:920px){.top,.cards,.rank-grid,.broker-grid.domestic,.broker-grid.foreign,.status{grid-template-columns:1fr}.date{text-align:left}.legend{justify-content:flex-start}.rank-list{grid-template-columns:1fr}.section-title{grid-template-columns:1fr}.top h1{font-size:34px}}
    """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>机构席位持仓共振日报 {html.escape(str(date_label))}</title>
<style>{css}</style>
</head>
<body>
<main class="page">
  <header class="top">
    <div>
      <div class="eyebrow">Institutional Positioning · Resonance Atlas</div>
      <h1>机构席位持仓共振日报</h1>
      <div class="sub">合并内资机构专题与外资专题：内资 8 席、外资 3 席按正向资金解读，家人席位按反向指标验证。重点观察内外资同向，以及家人原始方向相反后的三方共振。</div>
    </div>
    <div class="date">
      <b>{html.escape(str(date_label))}</b>
      <div class="sub">数据源：奇货可查 broker/position<br/>样本行数：{total_rows}</div>
      <div class="legend"><span><i class="dot red"></i> 偏多/加多</span><span><i class="dot green"></i> 偏空/加空</span><span><i class="dot gold"></i> 共振</span></div>
    </div>
  </header>

  <section class="section">
    <div class="section-title"><em>01</em><h2>三类资金摘要</h2><span>单位：手；方向分数 = 加多 + 减空 - 减多 - 加空</span></div>
    <div class="cards">
      <div class="card"><div class="k">机构合计方向</div><div class="v {direction_class(institutional_score)}">{signed(institutional_score)}</div><div class="s">内资 + 外资同向视为正向资金；当前为 {direction(institutional_score)}</div></div>
      {group_cards(domestic, "内资机构", "domestic")}
      {group_cards(foreign, "外资席位", "foreign")}
      <div class="card accent"><div class="k">三方强共振</div><div class="v">{triple_count} 个</div><div class="s">内外资同向且家人反向后同向；偏多 {triple_bull_count}，偏空 {triple_bear_count}。</div></div>
    </div>
  </section>

  <section class="section">
    <div class="section-title"><em>02</em><h2>三方共振净方向排行</h2><span>按商品板块分别列出前三净多、前三净空；计算口径 = 内资 + 外资 - 家人席位</span></div>
    <div class="rank-grid">
      <div class="rank-block"><h3>三方共振净偏多</h3><div class="rank-list">{net_cards(resonance, "bull", "三方共振净偏多")}</div></div>
      <div class="rank-block"><h3>三方共振净偏空</h3><div class="rank-list">{net_cards(resonance, "bear", "三方共振净偏空")}</div></div>
    </div>
    <div class="analysis-box">
      <h3>内资毛动作与净方向背离拆解</h3>
      <p class="hint">这里专门列出“单边动作看起来很大，但整体净方向相反或被另一边动作压过”的品种，并同步标注外资、家人反向是否验证。</p>
      <table>
        <thead><tr><th>品种</th><th>净方向</th><th class="num">内资净变化</th><th>反向毛动作</th><th class="num">外资</th><th class="num">家人反向</th><th>解读</th></tr></thead>
        <tbody>{divergence_rows(domestic, resonance, 10)}</tbody>
      </table>
    </div>
  </section>

  <section class="section">
    <div class="section-title"><em>03</em><h2>农产品天气风险预警</h2><span>奇货可查 AI天眼：{html.escape(str(weather_status.get('data_date', '-')))}；今日与未来预警分别展示</span></div>
    <table>
      <thead><tr><th>时点</th><th>品种</th><th>风险</th><th>风险类型 / 产地</th><th>天气事实</th><th>AI天眼盘面观察</th><th>席位资金验证</th></tr></thead>
      <tbody>{weather_risk_rows(weather, resonance)}</tbody>
    </table>
  </section>

  <section class="section">
    <div class="section-title"><em>04</em><h2>期货资金潮汐</h2><span>当前底表暂无行情涨跌字段，先以资金净流入/流出 × 总持仓增/减判断边际状态</span></div>
    <table>
      <thead><tr><th>品种</th><th>潮汐状态</th><th>资金净流</th><th>总持仓变化</th><th class="num">内资</th><th class="num">外资</th><th class="num">家人原始</th></tr></thead>
      <tbody>{tide_rows(resonance, 20)}</tbody>
    </table>
  </section>

  <section class="section">
    <div class="section-title"><em>05</em><h2>核心品种全景</h2><span>当前净持仓与今日边际变化分列；红为偏多，绿为偏空</span></div>
    <table>
      <thead><tr><th>品种</th><th>信号</th><th>内资变化</th><th>外资变化</th><th>家人原始变化</th><th class="num">家人反向</th><th>今日机构合计</th><th>当前净持仓</th><th class="num">总变化</th></tr></thead>
      <tbody>{progress_rows(resonance, 24)}</tbody>
    </table>
  </section>

  <section class="section">
    <div class="section-title"><em>06</em><h2>内外资同向 + 家人反向清单</h2><span>强共振优先排序，其次按家人反向验证强度排序</span></div>
    <table>
      <thead><tr><th>品种</th><th>共振类型</th><th class="num">内资方向</th><th class="num">外资方向</th><th class="num">家人原始</th><th class="num">家人反向</th><th class="num">机构合计</th><th class="num">强度</th></tr></thead>
      <tbody>{resonance_rows(resonance, 18)}</tbody>
    </table>
  </section>

  <section class="section">
    <div class="section-title"><em>07</em><h2>内资席位分拆</h2><span>每家内资席位最活跃品种</span></div>
    <div class="broker-grid domestic">{''.join(broker_panel(broker_summary, broker) for broker in DOMESTIC_BROKERS)}</div>
  </section>

  <section class="section">
    <div class="section-title"><em>08</em><h2>外资席位分拆</h2><span>三家外资席位最活跃品种</span></div>
    <div class="broker-grid foreign">{''.join(broker_panel(broker_summary, broker) for broker in FOREIGN_BROKERS)}</div>
  </section>

  <section class="section">
    <div class="section-title"><em>09</em><h2>抓取状态</h2><span>不同席位可能披露日期不同，结论以此处日期为准；天气预警 {html.escape(str(weather_status.get('current_alerts', 0)))} / {html.escape(str(weather_status.get('future_alerts', 0)))} 条</span></div>
    <div class="status">{status_cards(fetch_status)}</div>
  </section>

  <section class="section note">
    <b>阅读口径：</b>加多或减空计入偏多，减多或加空计入偏空。内资、外资作为正向资金；家人席位作为反向指标，所以“家人反向”列为家人原始方向乘以 -1。若后续这张机构专题稳定，可用它替代旧的全席位日报，只保留更聚焦的机构/家人共振框架。
  </section>

  <div class="foot">本报告仅为席位持仓数据整理，不构成投资建议。生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}。</div>
</main>
</body>
</html>"""


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_rows, fetch_status = fetch_rows()
    raw_rows.to_csv(DATA_DIR / "contract_rows_all.csv", index=False, encoding="utf-8-sig")
    rows = BASE.filter_commodity_rows(raw_rows)
    rows = add_flow_columns(rows)

    try:
        weather, weather_status = fetch_weather_risk()
    except Exception as exc:
        weather = pd.DataFrame()
        weather_status = {"data_date": "-", "current_alerts": 0, "future_alerts": 0, "error": str(exc)}

    domestic = summarize_group(rows, "内资")
    foreign = summarize_group(rows, "外资")
    family = summarize_group(rows, "家人")
    broker_summary = summarize_broker(rows)
    resonance = build_resonance(domestic, foreign, family)

    rows.to_csv(DATA_DIR / "contract_rows.csv", index=False, encoding="utf-8-sig")
    fetch_status.to_csv(DATA_DIR / "fetch_status.csv", index=False, encoding="utf-8-sig")
    domestic.to_csv(DATA_DIR / "domestic_variety_summary.csv", index=False, encoding="utf-8-sig")
    foreign.to_csv(DATA_DIR / "foreign_variety_summary.csv", index=False, encoding="utf-8-sig")
    family.to_csv(DATA_DIR / "family_variety_summary.csv", index=False, encoding="utf-8-sig")
    broker_summary.to_csv(DATA_DIR / "broker_variety_summary.csv", index=False, encoding="utf-8-sig")
    resonance.to_csv(DATA_DIR / "institutional_resonance.csv", index=False, encoding="utf-8-sig")
    weather.to_csv(DATA_DIR / "agri_weather_risk.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([weather_status]).to_csv(DATA_DIR / "agri_weather_fetch_status.csv", index=False, encoding="utf-8-sig")

    if not SKIP_REPORT_HTML:
        html_text = build_html(rows, fetch_status, domestic, foreign, family, broker_summary, resonance, weather, weather_status)
        (OUT_DIR / "report.html").write_text(html_text, encoding="utf-8")
        print(f"report: {OUT_DIR / 'report.html'}")
    else:
        print(f"data only: {DATA_DIR}")
    print(f"rows: {len(rows)}")
    print(f"triple resonance: {int(resonance['triple_resonance'].sum()) if not resonance.empty else 0}")
    print(f"domestic+foreign same: {int(resonance['domestic_foreign_same'].sum()) if not resonance.empty else 0}")


if __name__ == "__main__":
    main()
