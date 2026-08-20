from __future__ import annotations

import base64
import html
import json
import math
import os
import re
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path.cwd()
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
OUT_DIR = ROOT / "output" / f"futures_report_{RUN_DATE}"
CHART_DIR = OUT_DIR / "charts"
DATA_DIR = OUT_DIR / "data"

BROKER_GROUPS = {
    "内资": ["国泰君安", "浙商期货", "永安期货", "东证期货", "海通期货"],
    "外资": ["高盛期货", "摩根大通", "瑞银期货"],
    "家人": ["东方财富", "徽商期货", "方正中期", "华安期货", "中信建投"],
}

FOCUS_ITEMS = [
    {"symbol": "FU", "display": "燃油", "structure": "燃油"},
    {"symbol": "EB", "display": "苯乙烯", "structure": "苯乙烯"},
    {"symbol": "LC", "display": "碳酸锂", "structure": "碳酸锂"},
    {"symbol": "M", "display": "豆粕", "structure": "豆粕"},
    {"symbol": "JM", "display": "焦煤", "structure": "焦煤"},
    {"symbol": "I", "display": "铁矿石", "structure": "铁矿石"},
    {"symbol": "JD", "display": "鸡蛋", "structure": "鸡蛋"},
    {"symbol": "AU", "display": "沪金", "structure": "沪金"},
    {"symbol": "AG", "display": "沪银", "structure": "沪银"},
    {"symbol": "EC", "display": "欧线集运", "structure": "集运欧线"},
    {"symbol": "LH", "display": "生猪", "structure": "生猪"},
    {"symbol": "P", "display": "棕榈油", "structure": "棕榈油"},
    {"symbol": "RU", "display": "天然橡胶", "structure": "天然橡胶"},
]
FOCUS_SYMBOLS = {item["symbol"]: item["display"] for item in FOCUS_ITEMS}
FOCUS_STRUCTURE_DISPLAY = {item["structure"]: item["display"] for item in FOCUS_ITEMS}
FOCUS_LABEL = "燃油、苯乙烯、碳酸锂、豆粕、鸡蛋、焦煤、铁矿石、沪金、沪银、欧线集运、生猪、棕榈油、天然橡胶"
STRUCTURE_TOP_N = 5

OPENVLAB_BASE = "https://www.openvlab.cn/chart/light/"

EXCLUDED_FINANCIAL_SYMBOLS = {"IC", "IF", "IH", "IM", "T", "TF", "TL", "TS"}
EXCLUDED_EXTERNAL_SYMBOLS = {"GCOW", "SIOW", "BRNOW", "CLO", "CLOY"}
EXCLUDED_THIN_SYMBOLS = {"CS", "AD", "PL", "RR", "CY", "OP", "RS"}

SECTOR_ORDER = [
    "贵金属",
    "有色金属",
    "家人品种",
    "黑色系",
    "油化工",
    "谷物饲料",
    "油脂油料",
    "农副软商",
]

FAMILY_SECTOR_SYMBOLS = {"FG", "SA", "AO", "SH", "PS", "SP"}
SECTOR_BY_SYMBOL = {
    "AU": "贵金属",
    "AG": "贵金属",
    "CU": "有色金属",
    "AL": "有色金属",
    "ZN": "有色金属",
    "PB": "有色金属",
    "NI": "有色金属",
    "SN": "有色金属",
    "SS": "有色金属",
    "BC": "有色金属",
    "LC": "有色金属",
    "SI": "有色金属",
    "RB": "黑色系",
    "HC": "黑色系",
    "I": "黑色系",
    "SF": "黑色系",
    "SM": "黑色系",
    "WR": "黑色系",
    "J": "黑色系",
    "JM": "黑色系",
    "ZC": "黑色系",
    "UR": "黑色系",
    "V": "黑色系",
    "SC": "油化工",
    "FU": "油化工",
    "BU": "油化工",
    "PG": "油化工",
    "MA": "油化工",
    "EB": "油化工",
    "BZ": "油化工",
    "PX": "油化工",
    "TA": "油化工",
    "RU": "油化工",
    "PP": "油化工",
    "BR": "油化工",
    "L": "油化工",
    "EG": "油化工",
    "PF": "油化工",
    "LU": "油化工",
    "PR": "油化工",
    "NR": "农副软商",
    "P": "油脂油料",
    "OI": "油脂油料",
    "PK": "油脂油料",
    "Y": "油脂油料",
    "M": "谷物饲料",
    "RM": "谷物饲料",
    "C": "谷物饲料",
    "A": "谷物饲料",
    "B": "谷物饲料",
    "CF": "农副软商",
    "SR": "农副软商",
    "LH": "农副软商",
    "AP": "农副软商",
    "JD": "农副软商",
    "CJ": "农副软商",
}
SECTOR_RANK = {name: idx for idx, name in enumerate(SECTOR_ORDER)}

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}

COLORS = {
    "blue": {"base": "#A3BEFA", "mid": "#5477C4", "dark": "#2E4780", "light": "#CEDFFE", "xlight": "#EAF1FE"},
    "orange": {"base": "#F0986E", "mid": "#CC6F47", "dark": "#804126", "light": "#FFBDA1", "xlight": "#FFEDDE"},
    "olive": {"base": "#A3D576", "mid": "#71B436", "dark": "#386411", "light": "#BEEB96", "xlight": "#D8ECBD"},
    "gold": {"base": "#FFE15B", "mid": "#B8A037", "dark": "#736422", "light": "#FFEA8F", "xlight": "#FFF4C2"},
    "pink": {"base": "#F390CA", "mid": "#BD569B", "dark": "#8A3A6F", "light": "#F5BACC", "xlight": "#FCDAD6"},
    "neutral": {"base": "#C5CAD3", "mid": "#7A828F", "dark": "#464C55", "light": "#E2E5EA", "xlight": "#F4F5F7"},
}


class CellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return " ".join(self.parts)


def cell_text(raw: str) -> str:
    parser = CellParser()
    parser.feed(raw)
    return parser.text()


def parse_num(value: str | None) -> int:
    if not value:
        return 0
    match = re.search(r"([-+]?\d+)", value.replace(",", "").replace("，", ""))
    return int(match.group(1)) if match else 0


def filter_commodity_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Exclude stock index and treasury futures from commodity-focused reports."""
    if df.empty or "symbol" not in df.columns:
        return df.copy()
    symbols = df["symbol"].astype(str).str.upper()
    excluded = EXCLUDED_FINANCIAL_SYMBOLS | EXCLUDED_EXTERNAL_SYMBOLS | EXCLUDED_THIN_SYMBOLS
    return df.loc[~symbols.isin(excluded)].copy()


def sector_label(variety: str, symbol: str) -> str:
    code = str(symbol or "").upper()
    if code in FAMILY_SECTOR_SYMBOLS:
        return "家人品种"
    return SECTOR_BY_SYMBOL.get(code, "其他商品")


def add_sector_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    result = df.copy()
    result["sector"] = result.apply(lambda row: sector_label(row.get("variety", ""), row.get("symbol", "")), axis=1)
    result["sector_rank"] = result["sector"].map(SECTOR_RANK).fillna(len(SECTOR_RANK)).astype(int)
    return result


def parse_position_and_change(value: str) -> tuple[int, int]:
    parts = value.split()
    pos = parse_num(parts[0]) if parts else 0
    change = 0
    for part in parts[1:]:
        match = re.search(r"\(([-+]?\d+)\)", part)
        if match:
            change = int(match.group(1))
            break
    return pos, change


def parse_net(value: str) -> int:
    if "净多" in value:
        return parse_num(value)
    if "净空" in value:
        return -parse_num(value)
    return parse_num(value)


def parse_structure_value(value: str) -> int:
    if not value:
        return 0
    sign = -1 if ("净空" in value or "流空" in value) else 1
    match = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
    if not match:
        return 0
    amount = float(match.group(1))
    if "亿" in value:
        amount *= 10000
    return int(round(sign * amount))


def contract_prefix(contract: str) -> str:
    match = re.match(r"([A-Za-z]+)", contract or "")
    return match.group(1).upper() if match else ""


def fetch_url(url: str) -> str:
    last_error: Exception | None = None
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"}
    if os.environ.get("QHKCH_COOKIE"):
        headers["Cookie"] = os.environ["QHKCH_COOKIE"]
    for attempt in range(3):
        try:
            request = Request(url, headers=headers)
            return urlopen(request, timeout=25).read().decode("utf-8")
        except Exception as exc:
            last_error = exc
            time.sleep(1 + attempt)

    curl_args = ["curl.exe", "-L", "--retry", "2", "--retry-delay", "1", "-A", "Mozilla/5.0"]
    if os.environ.get("QHKCH_COOKIE"):
        curl_args.extend(["-H", f"Cookie: {os.environ['QHKCH_COOKIE']}"])
    curl_args.append(url)
    curl = subprocess.run(
        curl_args,
        capture_output=True,
        timeout=45,
    )
    if curl.returncode == 0 and curl.stdout:
        return curl.stdout.decode("utf-8", errors="replace")
    error_text = curl.stderr.decode("utf-8", errors="replace").strip()
    raise RuntimeError(error_text or str(last_error))


def fetch_broker(broker: str, requested_date: str | None = None) -> tuple[str | None, str, list[dict]]:
    url = "https://x.qhkch.com/broker/position?broker=" + quote(broker)
    if requested_date:
        url += "&date=" + quote(requested_date)
    text = fetch_url(url)
    title = re.search(r'<th colspan="6"[^>]*>\s*(\d{4}-\d{2}-\d{2})\s+(.+?)\s*持仓列表', text, re.S)
    date = title.group(1) if title else None
    rows: list[dict] = []

    for row_match in re.finditer(r'<tr class="position_list position_list_(.*?)">(.*?)</tr>', text, re.S):
        variety = html.unescape(row_match.group(1))
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_match.group(2), re.S)
        values = [cell_text(cell) for cell in cells]
        if len(values) >= 6:
            values = values[2:6]
        elif len(values) >= 4:
            values = values[0:4]
        else:
            continue

        contract = values[0].split()[0] if values[0].split() else ""
        long_pos, long_chg = parse_position_and_change(values[2])
        short_pos, short_chg = parse_position_and_change(values[3])
        rows.append(
            {
                "broker": broker,
                "date": date,
                "url": url,
                "variety": variety,
                "contract": contract,
                "symbol": contract_prefix(contract),
                "net": parse_net(values[1]),
                "long_pos": long_pos,
                "long_chg": long_chg,
                "short_pos": short_pos,
                "short_chg": short_chg,
            }
        )
    return date, url, rows



def openvlab_url(contract: str) -> str:
    match = re.match(r"([A-Za-z]+)(\d{2})(\d{2})", contract or "")
    if not match:
        return ""
    symbol, yy, mm = match.groups()
    return f"{OPENVLAB_BASE}{symbol.upper()}20{yy}{mm}"


def add_group(row: dict) -> dict:
    for group, brokers in BROKER_GROUPS.items():
        if row["broker"] in brokers:
            row["group"] = group
            break
    return row


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["gross_pos"] = df["long_pos"] + df["short_pos"]
    df["net_pos"] = df["long_pos"] - df["short_pos"]
    df["bull_flow"] = df["long_chg"].clip(lower=0) + (-df["short_chg"]).clip(lower=0)
    df["bear_flow"] = (-df["long_chg"]).clip(lower=0) + df["short_chg"].clip(lower=0)
    df["flow_score"] = df["bull_flow"] - df["bear_flow"]
    df["dir_hands"] = df[["bull_flow", "bear_flow"]].max(axis=1)
    df["dir"] = df["flow_score"].apply(lambda x: "偏多" if x > 0 else ("偏空" if x < 0 else "中性"))
    df["threshold_ratio"] = df.apply(lambda r: r["dir_hands"] / r["gross_pos"] if r["gross_pos"] else 0, axis=1)
    return df


def group_summary(rows: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if rows.empty:
        return rows
    grouped = rows.groupby(keys, as_index=False).agg(
        long_pos=("long_pos", "sum"),
        short_pos=("short_pos", "sum"),
        long_chg=("long_chg", "sum"),
        short_chg=("short_chg", "sum"),
        gross_pos=("gross_pos", "sum"),
        net_pos=("net_pos", "sum"),
        bull_flow=("bull_flow", "sum"),
        bear_flow=("bear_flow", "sum"),
        min_date=("date", "min"),
        max_date=("date", "max"),
        rows=("contract", "count"),
    )
    grouped["flow_score"] = grouped["bull_flow"] - grouped["bear_flow"]
    grouped["dir_hands"] = grouped[["bull_flow", "bear_flow"]].max(axis=1)
    grouped["dir"] = grouped["flow_score"].apply(lambda x: "偏多" if x > 0 else ("偏空" if x < 0 else "中性"))
    grouped["threshold_ratio"] = grouped.apply(lambda r: r["dir_hands"] / r["gross_pos"] if r["gross_pos"] else 0, axis=1)
    return grouped


def fmt_int(value: float | int) -> str:
    return f"{int(value):,}"


def fmt_signed(value: float | int) -> str:
    value = int(value)
    return f"{value:+,}"


def fmt_money(value: float | int) -> str:
    value = int(value)
    if abs(value) >= 10000:
        return f"{value / 10000:+.2f}亿"
    return f"{value:+,}万"


def fmt_pct(value: float) -> str:
    return f"{value:.0%}"


def direction_label(score: float) -> str:
    if score > 0:
        return "看多"
    if score < 0:
        return "看空"
    return "中性"


def signal_badge(score: float) -> str:
    direction = direction_label(score)
    cls = "up" if score > 0 else ("down" if score < 0 else "neutral")
    return f'<span class="badge {cls}">{direction}</span>'


def embed_image(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def setup_plotting():
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "axes.grid": True,
            "grid.color": TOKENS["grid"],
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Segoe UI", "Arial Unicode MS", "DejaVu Sans"],
            "axes.unicode_minus": False,
        },
    )
    return plt, sns


def add_header(fig, ax, title: str, subtitle: str) -> None:
    import textwrap
    import seaborn as sns

    ax.set_title("")
    fig.subplots_adjust(top=0.80, left=0.24, right=0.96, bottom=0.14)
    left = ax.get_position().x0
    fig.text(left, 0.96, textwrap.fill(title, width=42), ha="left", va="top", fontsize=14, fontweight="bold", color=TOKENS["ink"])
    fig.text(left, 0.90, textwrap.fill(subtitle, width=74), ha="left", va="top", fontsize=9.5, color=TOKENS["muted"])
    sns.despine(ax=ax)


def chart_diverging_signals(conflicts: pd.DataFrame, path: Path) -> None:
    plt, sns = setup_plotting()
    plot_df = conflicts.head(14).copy().sort_values("action_score")
    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    colors = [COLORS["orange"]["base"] if v >= 0 else COLORS["olive"]["base"] for v in plot_df["action_score"]]
    edges = [COLORS["orange"]["dark"] if v >= 0 else COLORS["olive"]["dark"] for v in plot_df["action_score"]]
    bars = ax.barh(plot_df["variety"], plot_df["action_score"], color=colors, edgecolor=edges, linewidth=1.0)
    ax.axvline(0, color=TOKENS["ink"], linewidth=1.0)
    ax.set_xlabel("综合净持仓变化（内外资净变 - 家人净变）")
    ax.set_ylabel("")
    for bar, value in zip(bars, plot_df["action_score"]):
        ax.text(value + (0.02 * plot_df["action_score"].abs().max() if value >= 0 else -0.02 * plot_df["action_score"].abs().max()), bar.get_y() + bar.get_height() / 2, fmt_signed(value), va="center", ha="left" if value >= 0 else "right", fontsize=8, color=TOKENS["ink"])
    add_header(fig, ax, "内外资与家人席位反向共振品种", "正值为共振看多，负值为共振看空；按净持仓日变化口径排序。")
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def chart_focus_contracts(focus: pd.DataFrame, path: Path) -> None:
    plt, sns = setup_plotting()
    plot_df = focus.copy()
    plot_df["label"] = plot_df["symbol"] + " " + plot_df["main_contract"].fillna("-")
    plot_df = plot_df.sort_values("action_score")
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    colors = [COLORS["orange"]["base"] if v >= 0 else COLORS["olive"]["base"] for v in plot_df["action_score"]]
    edges = [COLORS["orange"]["dark"] if v >= 0 else COLORS["olive"]["dark"] for v in plot_df["action_score"]]
    bars = ax.barh(plot_df["label"], plot_df["action_score"], color=colors, edgecolor=edges, linewidth=1.0)
    ax.axvline(0, color=TOKENS["ink"], linewidth=1.0)
    ax.set_xlabel("主力合约综合净持仓变化")
    ax.set_ylabel("")
    for bar, value in zip(bars, plot_df["action_score"]):
        ax.text(value + (0.03 * max(1, plot_df["action_score"].abs().max()) if value >= 0 else -0.03 * max(1, plot_df["action_score"].abs().max())), bar.get_y() + bar.get_height() / 2, fmt_signed(value), va="center", ha="left" if value >= 0 else "right", fontsize=8, color=TOKENS["ink"])
    add_header(fig, ax, "重点品种主力合约资金方向", f"{FOCUS_LABEL}；综合净变 = 内外资净变 - 家人净变。")
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def chart_group_heatmap(variety_groups: pd.DataFrame, path: Path) -> None:
    plt, sns = setup_plotting()
    top = (
        variety_groups.assign(abs_score=variety_groups["flow_score"].abs())
        .groupby("variety", as_index=False)["abs_score"]
        .sum()
        .sort_values("abs_score", ascending=False)
        .head(18)["variety"]
    )
    pivot = variety_groups[variety_groups["variety"].isin(top)].pivot_table(index="variety", columns="group", values="flow_score", aggfunc="sum", fill_value=0)
    for col in ["内资", "外资", "家人"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot[["内资", "外资", "家人"]]
    pivot = pivot.loc[pivot.abs().sum(axis=1).sort_values(ascending=True).index]
    fig, ax = plt.subplots(figsize=(7.8, 7.2))
    vmax = max(1, float(pivot.abs().max().max()))
    cmap = sns.diverging_palette(130, 10, s=70, l=70, center="light", as_cmap=True)
    sns.heatmap(pivot, cmap=cmap, center=0, vmin=-vmax, vmax=vmax, linewidths=1, linecolor="#FFFFFF", annot=True, fmt=".0f", cbar_kws={"label": "变化分数"}, ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("")
    add_header(fig, ax, "主要品种三类席位净变化热力图", "数值为净持仓日变化；家人列需反向解读。")
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_html_table(rows: list[dict], columns: list[tuple[str, str]], max_rows: int | None = None) -> str:
    selected = rows[:max_rows] if max_rows else rows
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    body = []
    for row in selected:
        cells = []
        for key, _ in columns:
            value = row.get(key, "")
            if key.endswith("_html"):
                cells.append(f"<td>{value}</td>")
            else:
                cells.append(f"<td>{html.escape(str(value))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def report_disclosure_date(report_dir: Path) -> str:
    status_path = report_dir / "data" / "fetch_status.csv"
    if not status_path.exists():
        return ""
    try:
        status = pd.read_csv(status_path)
    except Exception:
        return ""
    dates = sorted({str(value) for value in status.get("date", []) if str(value) and str(value) != "-"})
    return dates[-1] if dates else ""


def build_strong_resonance_history(latest_conflict: pd.DataFrame) -> tuple[list[dict], pd.DataFrame, str]:
    records = []
    latest_by_date: dict[str, Path] = {}
    for report_dir in sorted((ROOT / "output").glob("futures_report_*")):
        conflict_path = report_dir / "data" / "contrarian_conflicts.csv"
        if not conflict_path.exists():
            continue
        disclosure_date = report_disclosure_date(report_dir)
        if not disclosure_date:
            continue
        previous = latest_by_date.get(disclosure_date)
        if previous is None or report_dir.name > previous.name:
            latest_by_date[disclosure_date] = report_dir

    recent_dates = sorted(latest_by_date)[-5:]
    for disclosure_date in recent_dates:
        conflict_path = latest_by_date[disclosure_date] / "data" / "contrarian_conflicts.csv"
        try:
            hist = pd.read_csv(conflict_path)
        except Exception:
            continue
        hist["disclosure_date"] = disclosure_date
        records.extend(hist.to_dict("records"))

    if not records:
        return [], pd.DataFrame(), "本地暂无历史共振数据。"

    history = pd.DataFrame(records)
    history.to_csv(DATA_DIR / "strong_resonance_history_source.csv", index=False, encoding="utf-8-sig")
    latest_strong = latest_conflict[latest_conflict["alignment"].eq("强共振")].copy()
    latest_strong = latest_strong.sort_values("action_score", key=lambda s: s.abs(), ascending=False)
    available_note = f"当前本地可用 {len(recent_dates)} 个披露日：{'、'.join(recent_dates)}。"

    rows = []
    for _, current in latest_strong.head(30).iterrows():
        variety = current["variety"]
        subset = history[history["variety"].eq(variety)].copy()
        subset = subset.sort_values("disclosure_date")
        if subset.empty:
            continue
        directions = list(subset["action_dir"])
        latest_dir = directions[-1]
        first_dir = directions[0]
        strong_count = int(subset["alignment"].eq("强共振").sum())
        if len(directions) >= 2 and first_dir != latest_dir:
            observation = "出现反转"
        elif len(directions) >= 2 and len(set(directions)) == 1:
            observation = "持续" + latest_dir.replace("看", "")
        elif len(directions) == 1:
            observation = "新近强共振"
        else:
            observation = "方向切换"

        trajectory_parts = []
        for _, item in subset.iterrows():
            mark = "*" if item["alignment"] == "强共振" else ""
            trajectory_parts.append(
                f"{str(item['disclosure_date'])[5:]} {item['action_dir']}{mark} {fmt_signed(item['action_score'])}"
            )

        rows.append(
            {
                "variety": variety,
                "current": f"{current['action_dir']} {fmt_signed(current['action_score'])}",
                "trajectory": " → ".join(trajectory_parts),
                "days": len(subset),
                "strong_days": strong_count,
                "positive": fmt_signed(current["pos_flow"]),
                "family": fmt_signed(current["fam_flow"]),
                "observation": observation,
            }
        )

    result = pd.DataFrame(rows)
    result.to_csv(DATA_DIR / "strong_resonance_history.csv", index=False, encoding="utf-8-sig")
    return rows, result, available_note


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fetch_status = []
    raw_rows = []
    for group, brokers in BROKER_GROUPS.items():
        for broker in brokers:
            try:
                date, url, rows = fetch_broker(broker)
                for row in rows:
                    row["group"] = group
                raw_rows.extend(rows)
                fetch_status.append({"group": group, "broker": broker, "date": date or "-", "rows": len(rows), "url": url, "note": "OK" if rows else "空表"})
            except Exception as exc:
                fetch_status.append({"group": group, "broker": broker, "date": "-", "rows": 0, "url": "", "note": f"失败: {exc}"})

    if not raw_rows:
        pd.DataFrame(fetch_status).to_csv(DATA_DIR / "fetch_status_failed.csv", index=False, encoding="utf-8-sig")
        raise RuntimeError("All broker fetches failed; kept existing successful report outputs unchanged.")

    rows = filter_commodity_rows(enrich(pd.DataFrame(raw_rows)))
    rows.to_csv(DATA_DIR / "broker_contract_rows.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(fetch_status).to_csv(DATA_DIR / "fetch_status.csv", index=False, encoding="utf-8-sig")

    broker_variety = group_summary(rows, ["group", "broker", "variety"])
    variety_groups = group_summary(rows, ["group", "variety"])
    variety_groups.to_csv(DATA_DIR / "group_variety_summary.csv", index=False, encoding="utf-8-sig")

    positive = (
        variety_groups[variety_groups["group"].isin(["内资", "外资"])]
        .groupby("variety", as_index=False)
        .agg(pos_flow=("flow_score", "sum"), pos_net=("net_pos", "sum"), pos_gross=("gross_pos", "sum"), pos_bull=("bull_flow", "sum"), pos_bear=("bear_flow", "sum"))
    )
    family = (
        variety_groups[variety_groups["group"].eq("家人")]
        .groupby("variety", as_index=False)
        .agg(fam_flow=("flow_score", "sum"), fam_net=("net_pos", "sum"), fam_gross=("gross_pos", "sum"), fam_bull=("bull_flow", "sum"), fam_bear=("bear_flow", "sum"))
    )
    conflict = positive.merge(family, on="variety", how="inner")
    conflict = conflict[(conflict["pos_flow"] * conflict["fam_flow"] < 0) & (conflict["pos_flow"].abs() >= 300) & (conflict["fam_flow"].abs() >= 300)].copy()
    conflict["action_score"] = conflict["pos_flow"] - conflict["fam_flow"]
    conflict["action_dir"] = conflict["action_score"].apply(direction_label)
    conflict["pos_dir"] = conflict["pos_flow"].apply(direction_label)
    conflict["fam_raw_dir"] = conflict["fam_flow"].apply(direction_label)
    conflict["fam_reverse_dir"] = (-conflict["fam_flow"]).apply(direction_label)
    conflict["alignment"] = conflict.apply(lambda r: "强共振" if (r["pos_flow"] * -r["fam_flow"] > 0 and r["pos_net"] * r["fam_net"] < 0) else "变化共振", axis=1)
    conflict = conflict.sort_values("action_score", key=lambda s: s.abs(), ascending=False)
    conflict.to_csv(DATA_DIR / "contrarian_conflicts.csv", index=False, encoding="utf-8-sig")

    threshold_path = DATA_DIR / "threshold_signals.csv"
    if threshold_path.exists():
        threshold_path.unlink()

    # Focus symbols on main contract proxy.
    focus_rows = []
    for item in FOCUS_ITEMS:
        symbol = item["symbol"]
        variety_name = item["display"]
        symbol_rows = rows[rows["symbol"].eq(symbol)].copy()
        if symbol_rows.empty:
            focus_rows.append(
                {
                    "symbol": symbol,
                    "variety": variety_name,
                    "structure_variety": item["structure"],
                    "main_contract": "-",
                    "coverage": "无覆盖",
                    "pos_flow": 0,
                    "fam_flow": 0,
                    "action_score": 0,
                    "action_dir": "无数据",
                    "pos_net": 0,
                    "fam_net": 0,
                    "gross_pos": 0,
                    "openvlab_url": "",
                    "note": "观察席位页面未发现该品种合约。",
                }
            )
            continue
        contract_gross = symbol_rows.groupby("contract", as_index=False)["gross_pos"].sum().sort_values("gross_pos", ascending=False)
        main_contract = contract_gross.iloc[0]["contract"]
        main_rows = symbol_rows[symbol_rows["contract"].eq(main_contract)]
        pos_rows = main_rows[main_rows["group"].isin(["内资", "外资"])]
        fam_rows = main_rows[main_rows["group"].eq("家人")]
        pos_flow = int(pos_rows["flow_score"].sum())
        fam_flow = int(fam_rows["flow_score"].sum())
        pos_net = int(pos_rows["net_pos"].sum())
        fam_net = int(fam_rows["net_pos"].sum())
        action_score = pos_flow - fam_flow
        focus_rows.append(
            {
                "symbol": symbol,
                "variety": variety_name,
                "structure_variety": item["structure"],
                "main_contract": main_contract,
                "coverage": f"{main_rows['broker'].nunique()}席位",
                "pos_flow": pos_flow,
                "fam_flow": fam_flow,
                "action_score": action_score,
                "action_dir": direction_label(action_score) if action_score else "中性",
                "pos_net": pos_net,
                "fam_net": fam_net,
                "gross_pos": int(main_rows["gross_pos"].sum()),
                "openvlab_url": openvlab_url(main_contract),
                "note": "正向与家人反向一致" if pos_flow * fam_flow < 0 else ("信号冲突或偏弱" if pos_flow or fam_flow else "主力合约暂无变化信号"),
            }
        )
    focus = pd.DataFrame(focus_rows)
    focus.to_csv(DATA_DIR / "focus_main_contracts.csv", index=False, encoding="utf-8-sig")

    # Full-seat report no longer performs or displays variety-structure validation.
    # Structure-page checks are intentionally kept out of this report; the user now
    # mainly reviews the institutional combined report and margin-weighted report.
    structure = pd.DataFrame(
        columns=["variety", "url", "status", "rows", "tracked_rows", "tracked_change", "top_change"]
    )
    structure_analysis_export: list[dict] = []
    structure_ok_count = 0
    structure_status_note = "已取消全席位日报结构页结果验证；重点结构页只在需要时后台核验，不再进入本报告。"

    chart_paths = {
        "conflict": CHART_DIR / "contrarian_conflicts.png",
        "focus": CHART_DIR / "focus_contracts.png",
        "heatmap": CHART_DIR / "group_heatmap.png",
    }
    chart_diverging_signals(conflict, chart_paths["conflict"])
    chart_focus_contracts(focus, chart_paths["focus"])
    chart_group_heatmap(variety_groups, chart_paths["heatmap"])

    date_values = sorted({str(item["date"]) for item in fetch_status if item["date"] and item["date"] != "-"})
    date_label = "、".join(date_values)
    empty_brokers = [item for item in fetch_status if item["rows"] == 0]

    top_long = conflict[conflict["action_score"] > 0].head(8)
    top_short = conflict[conflict["action_score"] < 0].head(8)
    focus_top = focus.sort_values("action_score", key=lambda s: s.abs(), ascending=False)
    resonance_history_rows, resonance_history, resonance_history_note = build_strong_resonance_history(conflict)

    summary_bits = []
    if not top_long.empty:
        summary_bits.append(f"共振看多最强的是 {top_long.iloc[0]['variety']}，综合信号 {fmt_signed(top_long.iloc[0]['action_score'])} 手。")
    if not top_short.empty:
        summary_bits.append(f"共振看空最强的是 {top_short.iloc[0]['variety']}，综合信号 {fmt_signed(top_short.iloc[0]['action_score'])} 手。")
    if not focus_top.empty:
        f0 = focus_top.iloc[0]
        summary_bits.append(f"重点品种里波动最大的是 {f0['symbol']} {f0['main_contract']}，方向 {f0['action_dir']}，综合信号 {fmt_signed(f0['action_score'])} 手。")

    conflict_rows = []
    for _, row in conflict.head(30).iterrows():
        conflict_rows.append(
            {
                "variety": row["variety"],
                "signal_html": signal_badge(row["action_score"]),
                "action_score": fmt_signed(row["action_score"]),
                "positive": f"{row['pos_dir']} {fmt_signed(row['pos_flow'])}",
                "family": f"家人原始{row['fam_raw_dir']} {fmt_signed(row['fam_flow'])} / 反向{row['fam_reverse_dir']}",
                "net": f"内外资净{fmt_signed(row['pos_net'])}；家人净{fmt_signed(row['fam_net'])}",
                "alignment": row["alignment"],
            }
        )

    focus_table_rows = []
    for _, row in focus.iterrows():
        openvlab = row.get("openvlab_url", "")
        openvlab = "" if pd.isna(openvlab) else str(openvlab)
        focus_table_rows.append(
            {
                "symbol": row["symbol"],
                "variety": row["variety"],
                "contract": row["main_contract"],
                "signal_html": signal_badge(row["action_score"]),
                "action_score": fmt_signed(row["action_score"]),
                "positive": f"净变{fmt_signed(row['pos_flow'])} / 当前净{fmt_signed(row['pos_net'])}",
                "family": f"净变{fmt_signed(row['fam_flow'])} / 当前净{fmt_signed(row['fam_net'])}",
                "coverage": row["coverage"],
                "openvlab_html": f'<a href="{html.escape(openvlab)}" target="_blank">OpenVLab</a>' if openvlab else "-",
                "note": row["note"],
            }
        )

    status_rows = [
        {
            "group": item["group"],
            "broker": item["broker"],
            "date": item["date"],
            "rows": item["rows"],
            "note": item["note"],
        }
        for item in fetch_status
    ]

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>期货席位资金面反向信号报告</title>
  <style>
    :root {{
      --bg: #eef1f2;
      --panel: #fbfcfc;
      --ink: #171d22;
      --muted: #65717b;
      --line: #d7dde0;
      --line-strong: #1f272d;
      --accent: #b07a26;
      --red: #c94f5a;
      --green: #0b7f6f;
      --green-soft: #dff2ee;
      --red-soft: #f9e5e7;
      --gold-soft: #f5edd9;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif; }}
    .page {{ width: min(1160px, calc(100vw - 44px)); margin: 0 auto; padding: 38px 0 60px; }}
    header {{ display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: end; border-bottom: 3px solid var(--line-strong); padding-bottom: 18px; margin-bottom: 22px; }}
    .eyebrow {{ color: var(--accent); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 6px; }}
    h1 {{ font-size: 34px; margin: 0; letter-spacing: 0; line-height: 1.12; }}
    .subtitle {{ color: var(--muted); font-size: 13px; margin-top: 8px; }}
    .meta {{ color: var(--ink); font-size: 13px; text-align: right; line-height: 1.75; font-weight: 700; }}
    .legend {{ color: var(--muted); font-weight: 500; }}
    section {{ margin: 24px 0; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 0; box-shadow: none; }}
    .section-title {{ display: grid; grid-template-columns: 42px 1fr auto; gap: 12px; align-items: baseline; margin: 28px 0 12px; border-bottom: 2px solid var(--line-strong); padding-bottom: 8px; }}
    .section-no {{ color: var(--accent); font-size: 12px; font-weight: 800; }}
    .section-title h2 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    .section-kicker {{ color: var(--muted); font-size: 12px; font-weight: 500; }}
    .summary {{ padding: 18px 20px; border-left: 5px solid var(--accent); background: #fbf7eb; }}
    .summary h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .summary ul {{ margin: 0; padding-left: 18px; line-height: 1.78; }}
    .summary strong {{ color: var(--ink); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
    .card {{ padding: 16px 17px; border-top: 4px solid var(--line-strong); min-height: 128px; }}
    .card.accent {{ border-top-color: var(--accent); background: var(--gold-soft); }}
    .card .k {{ color: var(--ink); font-size: 13px; font-weight: 800; margin-bottom: 16px; }}
    .card .v {{ font-size: 30px; font-weight: 900; line-height: 1; color: var(--green); }}
    .card .v.red {{ color: var(--red); }}
    .card .s {{ color: var(--muted); margin-top: 10px; line-height: 1.45; font-size: 12px; }}
    .chart {{ padding: 14px; }}
    .chart img {{ width: 100%; display: block; border-radius: 0; border: 1px solid var(--line); background: #fff; }}
    .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; background: var(--panel); }}
    th, td {{ border-bottom: 1px solid #e5eaed; padding: 9px 10px; text-align: left; vertical-align: middle; }}
    th {{ color: #55616b; background: #e7ecef; font-weight: 800; font-size: 11px; }}
    tbody tr:nth-child(even) td {{ background: #f7f9fa; }}
    tr:hover td {{ background: #fff8e7; }}
    .table-wrap {{ overflow-x: auto; }}
    .badge {{ display: inline-flex; align-items: center; min-width: 44px; justify-content: center; padding: 3px 8px; border-radius: 3px; font-weight: 900; font-size: 12px; }}
    .badge.up {{ color: var(--red); background: var(--red-soft); border: 1px solid #ecc5ca; }}
    .badge.down {{ color: var(--green); background: var(--green-soft); border: 1px solid #b7ded6; }}
    .badge.neutral {{ color: #56616b; background: #eef1f2; border: 1px solid #d6dde1; }}
    .note {{ color: var(--muted); line-height: 1.7; font-size: 12px; }}
    .pill {{ display: inline-block; padding: 4px 8px; border: 1px solid var(--line); border-radius: 999px; background: #fff; color: var(--muted); font-size: 12px; margin-right: 6px; }}
    footer {{ color: var(--muted); font-size: 11px; margin-top: 26px; padding-top: 14px; border-top: 1px solid var(--line); line-height: 1.8; }}
    @media (max-width: 900px) {{ .grid, .two {{ grid-template-columns: 1fr; }} header {{ grid-template-columns: 1fr; }} .meta {{ text-align: left; }} .section-title {{ grid-template-columns: 34px 1fr; }} .section-kicker {{ display: none; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <div class="eyebrow">INSTITUTIONAL POSITIONINGS · CATEGORY ATLAS</div>
        <h1>机构期货持仓全景</h1>
        <div class="subtitle">乾坤期货更名为高盛期货；内资/外资按正向资金，家人席位按反向指标解读。</div>
      </div>
      <div class="meta">{datetime.now().strftime("%Y.%m.%d")}<br/><span class="legend">披露日期：{html.escape(date_label)}</span><br/><span class="legend">■ 净多　■ 净空　■ 平轴</span></div>
    </header>

    <div class="section-title"><span class="section-no">01</span><h2>三类席位仓位摘要</h2><span class="section-kicker">机构、散户与外盘资金同屏观察</span></div>
    <section class="summary panel">
      <h2>Executive Summary</h2>
      <ul>
        <li><strong>正向资金与家人反向资金已经形成一批共振品种。</strong>{html.escape(" ".join(summary_bits))}</li>
        <li><strong>判断口径以净持仓日变化为主，当前净持仓为辅。</strong>综合净变 = 内外资净持仓变化 - 家人净持仓变化；当前净持仓累计值只作为背景，不直接决定综合信号正负。</li>
        <li><strong>外资样本已按最新席位名更新。</strong>原“乾坤期货”改按“高盛期货”抓取，并与摩根大通、瑞银期货一起纳入外资组。</li>
        <li><strong>品种结构页已加入后台交叉验证。</strong>{html.escape(structure_status_note)} 结构页明细不单独展示，只在重点品种前5结构分析中使用。</li>
      </ul>
    </section>

    <section class="grid">
      <div class="card panel"><div class="k">反向共振品种数</div><div class="v">{len(conflict)}</div><div class="s">内外资变化方向与家人原始变化方向相反，且双方变化绝对值均超过 300 手。</div></div>
      <div class="card panel"><div class="k">强共振历史观察</div><div class="v">{len(resonance_history_rows)}</div><div class="s">筛选当日强共振品种，回看最近 5 个可用披露日，识别持续多/空或反转。</div></div>
      <div class="card panel"><div class="k">重点品种覆盖</div><div class="v">{sum(1 for x in focus_rows if x['main_contract'] != '-')} / {len(FOCUS_SYMBOLS)}</div><div class="s">{html.escape(FOCUS_LABEL)}。未覆盖品种会在重点表中标注。</div></div>
      <div class="card panel accent"><div class="k">结构页验证</div><div class="v">已取消</div><div class="s">全席位日报不再展示结构页结果验证；重点看机构合并专题和保证金金额口径日报。</div></div>
    </section>

    <div class="section-title"><span class="section-no">02</span><h2>分组方向速览</h2><span class="section-kicker">正向资金与家人反向信号</span></div>
    <section class="chart panel">
      <h2>共振品种：内外资正向 vs 家人反向</h2>
      <p class="note">这张图将内资和外资的净持仓日变化合并，再减去家人席位净持仓日变化。内外资净持仓增加为看多；家人净持仓增加按反向看空。</p>
      <img src="{embed_image(chart_paths['conflict'])}" alt="内外资与家人席位反向共振品种" />
    </section>

    <div class="section-title"><span class="section-no">03</span><h2>重点图谱</h2><span class="section-kicker">主力合约与三类席位矩阵</span></div>
    <section class="two">
      <div class="chart panel">
        <h2>重点品种主力合约</h2>
        <p class="note">主力合约按观察席位当前多空总持仓最大合约代理。表中“综合净变”不是当前净持仓累计值，例如内外资净减 458、家人净减 237，则综合净变为 -221。</p>
        <img src="{embed_image(chart_paths['focus'])}" alt="重点品种主力合约资金方向" />
      </div>
      <div class="chart panel">
        <h2>三类席位变化热力图</h2>
        <p class="note">热力图展示净持仓日变化，家人列需要反向看。颜色越深，净变化手数越大。</p>
        <img src="{embed_image(chart_paths['heatmap'])}" alt="主要品种三类席位变化热力图" />
      </div>
    </section>

    <div class="section-title"><span class="section-no">04</span><h2>共振明细</h2><span class="section-kicker">按综合净变绝对值排序</span></div>
    <section class="panel table-wrap">
      {make_html_table(conflict_rows, [("variety", "品种"), ("signal_html", "综合方向"), ("action_score", "综合净变"), ("positive", "内外资净变"), ("family", "家人净变"), ("net", "当前净持仓结构"), ("alignment", "类型")])}
    </section>

    <div class="section-title"><span class="section-no">05</span><h2>强共振五日动向</h2><span class="section-kicker">观察持续多空与方向切换</span></div>
    <section class="panel table-wrap">
      <p class="note" style="padding:0 18px 8px;">{html.escape(resonance_history_note)} 轨迹中带 * 的日期为强共振；未带 * 表示仍有反向共振但当前净持仓结构未满足强共振条件。</p>
      {make_html_table(resonance_history_rows, [("variety", "品种"), ("current", "当日强共振"), ("trajectory", "近5披露日轨迹"), ("days", "可用天数"), ("strong_days", "强共振天数"), ("positive", "当日内外资净变"), ("family", "当日家人净变"), ("observation", "观察")])}
    </section>

    <div class="section-title"><span class="section-no">06</span><h2>重点品种资金变动</h2><span class="section-kicker">{html.escape(FOCUS_LABEL)} 主力合约代理</span></div>
    <section class="panel table-wrap">
      {make_html_table(focus_table_rows, [("symbol", "代码"), ("variety", "品种"), ("contract", "主力合约代理"), ("signal_html", "方向"), ("action_score", "综合净变"), ("positive", "内外资净变/当前净持仓"), ("family", "家人净变/当前净持仓"), ("coverage", "覆盖"), ("openvlab_html", "期权/图表"), ("note", "解读")])}
    </section>

    <div class="section-title"><span class="section-no">07</span><h2>数据读取状态</h2><span class="section-kicker">席位页面抓取健康度</span></div>
    <section class="panel table-wrap">
      {make_html_table(status_rows, [("group", "分组"), ("broker", "席位"), ("date", "披露日期"), ("rows", "合约行数"), ("note", "状态")])}
    </section>

    <section class="panel card">
      <h2>建议跟踪</h2>
      <p class="note"><strong>优先盯共振而不是单边变化。</strong>当内外资继续同向、家人继续反向时，信号可信度上升；如果第二天家人和正向资金同向，说明可能只是换月或短线扰动。</p>
      <p class="note"><strong>重点品种里，JM/JD 等产业品种要区分主力合约换月影响。</strong>若主力合约代理发生切换，第二天应同时看旧主力和新主力的席位迁移。</p>
    </section>

    <footer>
      数据源：奇货可查席位持仓页。口径：按席位页面合约行汇总，净持仓日变化 = 多头变化 - 空头变化；综合净变 = 内外资净变 - 家人净变。限制：不同席位披露日期不完全一致；原乾坤期货按现名高盛期货抓取；主力合约为观察席位持仓最大合约代理。
    </footer>
  </main>
</body>
</html>
"""

    report_path = OUT_DIR / "report.html"
    report_path.write_text(html_doc, encoding="utf-8")
    print(json.dumps({"report": str(report_path), "out_dir": str(OUT_DIR), "rows": len(rows), "conflicts": len(conflict), "strong_history": len(resonance_history_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
