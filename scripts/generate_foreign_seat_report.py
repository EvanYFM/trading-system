from __future__ import annotations

import html
import importlib.util
import math
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path.cwd()
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
OUT_DIR = ROOT / "output" / f"foreign_seat_report_{RUN_DATE}"
DATA_DIR = OUT_DIR / "data"

FOREIGN_BROKERS = ["高盛期货", "摩根大通", "瑞银期货"]
FAMILY_BROKERS = ["东方财富", "徽商期货", "方正中期", "华安期货", "中信建投"]


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


def pct(value: float) -> str:
    return f"{value:.0%}"


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


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value)


def fetch_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    fetch_status: list[dict] = []
    rows: list[dict] = []
    for group, brokers in [("外资", FOREIGN_BROKERS), ("家人", FAMILY_BROKERS)]:
        for broker in brokers:
            try:
                date, url, broker_rows = BASE.fetch_broker(broker)
                fetch_status.append({"group": group, "broker": broker, "date": date, "rows": len(broker_rows), "url": url, "note": "OK"})
                for row in broker_rows:
                    row = dict(row)
                    row["group"] = group
                    rows.append(row)
            except Exception as exc:
                fetch_status.append({"group": group, "broker": broker, "date": "", "rows": 0, "url": "", "note": f"ERROR: {exc}"})
    return pd.DataFrame(rows), pd.DataFrame(fetch_status)


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
    return df


def summarize_group(df: pd.DataFrame, group: str) -> pd.DataFrame:
    group_df = df[df["group"] == group]
    if group_df.empty:
        return pd.DataFrame()
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
    grouped["activity"] = grouped["add_long"] + grouped["add_short"] + grouped["reduce_long"] + grouped["reduce_short"]
    grouped["add_activity"] = grouped["add_long"] + grouped["add_short"]
    grouped["add_long_share"] = grouped.apply(lambda r: r["add_long"] / r["add_activity"] if r["add_activity"] else 0, axis=1)
    grouped["dir"] = grouped["flow_score"].map(direction)
    return grouped.sort_values("activity", ascending=False)


def summarize_broker(df: pd.DataFrame) -> pd.DataFrame:
    foreign = df[df["group"] == "外资"]
    if foreign.empty:
        return pd.DataFrame()
    grouped = foreign.groupby(["broker", "variety", "symbol"], as_index=False).agg(
        add_long=("add_long", "sum"),
        add_short=("add_short", "sum"),
        reduce_long=("reduce_long", "sum"),
        reduce_short=("reduce_short", "sum"),
        flow_score=("flow_score", "sum"),
        activity=("flow_score", lambda s: 0),
    )
    grouped["activity"] = grouped["add_long"] + grouped["add_short"] + grouped["reduce_long"] + grouped["reduce_short"]
    grouped["dir"] = grouped["flow_score"].map(direction)
    return grouped.sort_values(["broker", "activity"], ascending=[True, False])


def build_resonance(foreign: pd.DataFrame, family: pd.DataFrame) -> pd.DataFrame:
    merged = foreign.merge(
        family[["variety", "symbol", "flow_score", "bull_flow", "bear_flow", "add_long", "add_short", "activity"]].rename(
            columns={
                "flow_score": "family_flow_score",
                "bull_flow": "family_bull_flow",
                "bear_flow": "family_bear_flow",
                "add_long": "family_add_long",
                "add_short": "family_add_short",
                "activity": "family_activity",
            }
        ),
        on=["variety", "symbol"],
        how="left",
    )
    for col in ["family_flow_score", "family_bull_flow", "family_bear_flow", "family_add_long", "family_add_short", "family_activity"]:
        merged[col] = merged[col].fillna(0)
    merged = merged.rename(
        columns={
            "flow_score": "foreign_flow_score",
            "bull_flow": "foreign_bull_flow",
            "bear_flow": "foreign_bear_flow",
            "add_long": "foreign_add_long",
            "add_short": "foreign_add_short",
            "activity": "foreign_activity",
        }
    )
    merged["family_reverse_score"] = -merged["family_flow_score"]
    merged["signal_score"] = merged["foreign_flow_score"] + merged["family_reverse_score"]
    merged["is_resonance"] = merged.apply(
        lambda r: r["foreign_flow_score"] != 0
        and r["family_flow_score"] != 0
        and math.copysign(1, r["foreign_flow_score"]) == math.copysign(1, -r["family_flow_score"]),
        axis=1,
    )
    merged["resonance_dir"] = merged["signal_score"].map(direction)
    merged["resonance_strength"] = merged[["foreign_flow_score", "family_reverse_score"]].abs().min(axis=1)
    merged["total_activity"] = merged["foreign_activity"] + merged["family_activity"]
    return merged.sort_values(["is_resonance", "resonance_strength", "total_activity"], ascending=[False, False, False])


def bar_pair(add_long: float, add_short: float) -> str:
    total = add_long + add_short
    if total <= 0:
        return '<div class="stack muted"><span style="width:50%"></span><span style="width:50%"></span></div>'
    long_pct = max(3, round(add_long / total * 100)) if add_long else 0
    short_pct = max(3, 100 - long_pct) if add_short else 0
    if add_long and not add_short:
        long_pct, short_pct = 100, 0
    if add_short and not add_long:
        long_pct, short_pct = 0, 100
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
    cls = direction_class(value)
    return f'<div class="flowbar"><i class="{cls}" style="width:{width}%"></i></div>'


def rows_for_progress(df: pd.DataFrame, limit: int = 18) -> str:
    selected = df.sort_values("add_activity", ascending=False).head(limit)
    if selected.empty:
        return '<tr><td colspan="7" class="muted-text">无可用数据</td></tr>'
    output = []
    max_score = max(selected["flow_score"].abs().max(), 1)
    for _, r in selected.iterrows():
        output.append(
            f"""
            <tr>
              <td><b>{html.escape(str(r['variety']))}</b><span>{html.escape(str(r['symbol']))}</span></td>
              <td class="num red">{unsigned(r['foreign_add_long']) if 'foreign_add_long' in r else unsigned(r['add_long'])}</td>
              <td class="num green">{unsigned(r['foreign_add_short']) if 'foreign_add_short' in r else unsigned(r['add_short'])}</td>
              <td>{bar_pair(r['foreign_add_long'] if 'foreign_add_long' in r else r['add_long'], r['foreign_add_short'] if 'foreign_add_short' in r else r['add_short'])}</td>
              <td class="num {direction_class(r['flow_score'])}">{signed(r['flow_score'])}</td>
              <td>{mini_flow_bar(r['flow_score'], max_score)}</td>
              <td><span class="pill {direction_class(r['flow_score'])}">{direction(r['flow_score'])}</span></td>
            </tr>
            """
        )
    return "\n".join(output)


def top_cards(df: pd.DataFrame, key: str, label: str, limit: int = 6) -> str:
    selected = df[df[key] > 0].sort_values(key, ascending=False).head(limit)
    if selected.empty:
        return '<div class="empty">无明显品种</div>'
    cards = []
    max_value = max(selected[key].max(), 1)
    for _, r in selected.iterrows():
        cls = "red" if key == "add_long" else "green"
        width = max(8, r[key] / max_value * 100)
        cards.append(
            f"""
            <div class="rank-card">
              <div class="rank-head"><b>{html.escape(str(r['variety']))}</b><span>{html.escape(str(r['symbol']))}</span></div>
              <div class="rank-value {cls}">{unsigned(r[key])}</div>
              <div class="rank-track"><i class="{cls}" style="width:{width}%"></i></div>
              <div class="rank-sub">{html.escape(label)} / 净方向 {signed(r['flow_score'])}</div>
            </div>
            """
        )
    return "\n".join(cards)


def broker_panel(broker_df: pd.DataFrame, broker: str) -> str:
    part = broker_df[broker_df["broker"] == broker].sort_values("activity", ascending=False).head(8)
    if part.empty:
        return f'<div class="broker-card"><h3>{html.escape(broker)}</h3><div class="empty">无数据</div></div>'
    rows = []
    max_activity = max(part["activity"].max(), 1)
    for _, r in part.iterrows():
        width = max(4, r["activity"] / max_activity * 100)
        cls = direction_class(r["flow_score"])
        rows.append(
            f"""
            <div class="broker-row">
              <div><b>{html.escape(str(r['variety']))}</b><span>{html.escape(str(r['symbol']))}</span></div>
              <div class="broker-meter"><i class="{cls}" style="width:{width}%"></i></div>
              <div class="num {cls}">{signed(r['flow_score'])}</div>
            </div>
            """
        )
    return f'<div class="broker-card"><h3>{html.escape(broker)}</h3>{"".join(rows)}</div>'


def scatter_svg(resonance: pd.DataFrame) -> str:
    plot = resonance[resonance["foreign_activity"] > 0].sort_values("total_activity", ascending=False).head(42).copy()
    if plot.empty:
        return '<div class="empty">无可用共振地图数据</div>'

    width, height = 880, 520
    pad_l, pad_r, pad_t, pad_b = 96, 40, 48, 78
    max_x = max(plot["foreign_flow_score"].abs().max(), 1)
    max_y = max(plot["family_reverse_score"].abs().max(), 1)
    max_size = max(plot["total_activity"].max(), 1)

    def sx(v):
        return pad_l + (v + max_x) / (2 * max_x) * (width - pad_l - pad_r)

    def sy(v):
        return pad_t + (max_y - v) / (2 * max_y) * (height - pad_t - pad_b)

    circles = []
    for _, r in plot.iterrows():
        x = sx(r["foreign_flow_score"])
        y = sy(r["family_reverse_score"])
        radius = 6 + math.sqrt(r["total_activity"] / max_size) * 18
        cls = "res-bull" if r["is_resonance"] and r["signal_score"] > 0 else ("res-bear" if r["is_resonance"] else "split")
        circles.append(
            f"""
            <g class="point {cls}">
              <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}"><title>{html.escape(str(r['variety']))} 外资{signed(r['foreign_flow_score'])} / 家人反向{signed(r['family_reverse_score'])}</title></circle>
              <text x="{x:.1f}" y="{y - radius - 5:.1f}">{html.escape(str(r['symbol']))}</text>
            </g>
            """
        )

    x0, y0 = sx(0), sy(0)
    return f"""
    <svg class="map" viewBox="0 0 {width} {height}" role="img" aria-label="外资与家人反向共振地图">
      <rect x="0" y="0" width="{width}" height="{height}" rx="8"></rect>
      <line class="axis" x1="{x0:.1f}" y1="{pad_t}" x2="{x0:.1f}" y2="{height - pad_b}"></line>
      <line class="axis" x1="{pad_l}" y1="{y0:.1f}" x2="{width - pad_r}" y2="{y0:.1f}"></line>
      <text class="quad" x="{pad_l + 12}" y="{pad_t + 22}">外资偏空 / 家人反向偏多</text>
      <text class="quad" x="{width - pad_r - 232}" y="{pad_t + 22}">偏多共振</text>
      <text class="quad" x="{pad_l + 12}" y="{height - pad_b - 14}">偏空共振</text>
      <text class="quad" x="{width - pad_r - 268}" y="{height - pad_b - 14}">外资偏多 / 家人反向偏空</text>
      {''.join(circles)}
      <text class="axis-label" x="{width / 2}" y="{height - 26}">外资资金方向：左偏空，右偏多</text>
      <text class="axis-label rotate" x="-{height / 2}" y="24">家人反向指标方向：下偏空，上偏多</text>
    </svg>
    """


def resonance_rows(resonance: pd.DataFrame, limit: int = 16) -> str:
    selected = resonance[resonance["is_resonance"]].head(limit)
    if selected.empty:
        return '<tr><td colspan="8" class="muted-text">暂无外资与家人反向后的同向共振</td></tr>'
    max_abs = max(selected["signal_score"].abs().max(), 1)
    rows = []
    for _, r in selected.iterrows():
        rows.append(
            f"""
            <tr>
              <td><b>{html.escape(str(r['variety']))}</b><span>{html.escape(str(r['symbol']))}</span></td>
              <td><span class="pill {direction_class(r['signal_score'])}">{direction(r['signal_score'])}</span></td>
              <td class="num {direction_class(r['foreign_flow_score'])}">{signed(r['foreign_flow_score'])}</td>
              <td class="num {direction_class(r['family_flow_score'])}">{signed(r['family_flow_score'])}</td>
              <td class="num {direction_class(r['family_reverse_score'])}">{signed(r['family_reverse_score'])}</td>
              <td class="num">{unsigned(r['resonance_strength'])}</td>
              <td>{mini_flow_bar(r['signal_score'], max_abs)}</td>
              <td>{unsigned(r['total_activity'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def build_html(
    rows: pd.DataFrame,
    fetch_status: pd.DataFrame,
    foreign: pd.DataFrame,
    family: pd.DataFrame,
    broker_summary: pd.DataFrame,
    resonance: pd.DataFrame,
) -> str:
    dates = sorted(d for d in fetch_status["date"].dropna().unique() if d)
    date_label = dates[-1] if dates else RUN_DATE
    foreign_rows = int(fetch_status[fetch_status["group"] == "外资"]["rows"].sum())
    family_rows = int(fetch_status[fetch_status["group"] == "家人"]["rows"].sum())
    foreign_net = int(foreign["flow_score"].sum()) if not foreign.empty else 0
    foreign_add_long = int(foreign["add_long"].sum()) if not foreign.empty else 0
    foreign_add_short = int(foreign["add_short"].sum()) if not foreign.empty else 0
    resonance_count = int(resonance["is_resonance"].sum()) if not resonance.empty else 0
    top_bull = foreign.sort_values("flow_score", ascending=False).head(1)
    top_bear = foreign.sort_values("flow_score").head(1)
    top_bull_text = f"{top_bull.iloc[0]['variety']} {signed(top_bull.iloc[0]['flow_score'])}" if not top_bull.empty else "-"
    top_bear_text = f"{top_bear.iloc[0]['variety']} {signed(top_bear.iloc[0]['flow_score'])}" if not top_bear.empty else "-"

    status_cards = "".join(
        f'<div class="status-row"><b>{html.escape(str(r.broker))}</b><span>{html.escape(str(r.date))}</span><em>{int(r.rows)}行</em></div>'
        for r in fetch_status.itertuples()
    )

    css = """
    :root{--bg:#f3f5f7;--panel:#fff;--ink:#1d232d;--muted:#6c7481;--line:#dfe4ea;--gold:#b8842b;--red:#c94c5a;--red2:#f7dfe2;--green:#087b68;--green2:#dff0eb;--blue:#426f9c;--soft:#f7f2e4}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;letter-spacing:0}
    .page{width:min(1180px,calc(100vw - 28px));margin:0 auto;padding:42px 0 54px}.top{display:grid;grid-template-columns:1fr auto;gap:24px;align-items:start;border-bottom:3px solid #202733;padding-bottom:24px}
    .eyebrow{font-size:12px;color:var(--gold);font-weight:800;text-transform:uppercase}.top h1{font-size:42px;line-height:1.05;margin:8px 0 8px}.sub{color:var(--muted);font-size:15px}.date{text-align:right}.date b{font-size:28px}.legend{display:flex;gap:12px;justify-content:flex-end;margin-top:12px;color:var(--muted);font-size:12px}.dot{width:9px;height:9px;border-radius:99px;display:inline-block}.dot.red,.rank-track i.red{background:var(--red)}.dot.green,.rank-track i.green{background:var(--green)}.dot.gold{background:var(--gold)}
    .section{margin-top:34px}.section-title{display:grid;grid-template-columns:42px 1fr auto;align-items:end;gap:16px;border-bottom:2px solid #1f2630;padding-bottom:10px;margin-bottom:16px}.section-title em{font-style:normal;color:var(--gold);font-weight:800}.section-title h2{font-size:24px;margin:0}.section-title span{color:var(--muted);font-size:12px}
    .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:var(--panel);border-top:4px solid #202733;padding:20px;min-height:132px}.card.accent{background:var(--soft);border-top-color:var(--gold)}.k{font-size:13px;color:var(--muted);font-weight:700}.v{font-size:34px;line-height:1.1;margin-top:12px;font-weight:850}.s{font-size:12px;color:var(--muted);margin-top:8px}.red,.bull{color:var(--red)}.green,.bear{color:var(--green)}.flat{color:var(--muted)}
    .rank-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.rank-list{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.rank-card{background:#fff;border:1px solid var(--line);padding:14px}.rank-head{display:flex;align-items:baseline;justify-content:space-between}.rank-head b{font-size:17px}.rank-head span,td span{display:block;color:var(--muted);font-size:11px;margin-top:2px}.rank-value{font-size:25px;font-weight:850;margin-top:8px}.rank-track{height:8px;background:#eef1f4;border-radius:99px;overflow:hidden;margin-top:9px}.rank-track i{height:100%;display:block;border-radius:99px}.rank-sub{font-size:11px;color:var(--muted);margin-top:8px}.empty,.muted-text{color:var(--muted);font-size:13px}
    table{width:100%;border-collapse:collapse;background:#fff}th{font-size:12px;text-align:left;color:#4d5663;background:#eef2f5;border-bottom:1px solid var(--line);padding:10px}td{border-bottom:1px solid #edf0f3;padding:11px 10px;vertical-align:middle}.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:760}.stack{height:12px;background:#edf1f4;border-radius:99px;display:flex;overflow:hidden;min-width:150px}.stack span{height:100%;display:block}.stack .long{background:var(--red)}.stack .short{background:var(--green)}.stack.muted span:first-child{background:#d9dee5}.stack.muted span:last-child{background:#c8ced6}.pill{display:inline-block;border-radius:99px;padding:4px 9px;font-size:12px;font-weight:800}.pill.bull{background:var(--red2);color:var(--red)}.pill.bear{background:var(--green2);color:var(--green)}.pill.flat{background:#edf1f4;color:var(--muted)}
    .flowbar{height:8px;background:#edf1f4;border-radius:99px;overflow:hidden}.flowbar i{display:block;height:100%;border-radius:99px}.flowbar .bull{background:var(--red)}.flowbar .bear{background:var(--green)}.flowbar .flat{background:#b4bcc7}
    .map-wrap{background:#fff;border:1px solid var(--line);padding:12px;display:grid;grid-template-columns:1fr 230px;gap:12px}.map{width:100%;height:auto}.map rect{fill:#fafbfc}.axis{stroke:#cfd6de;stroke-dasharray:5 4}.axis-label,.quad{fill:#687281;font-size:14px}.rotate{transform:rotate(-90deg);transform-origin:0 0}.point circle{stroke:#28323e;stroke-width:1.4;opacity:.82}.point text{font-size:12px;font-weight:850;fill:#29313b;text-anchor:middle}.point.res-bull circle{fill:#d98992}.point.res-bear circle{fill:#58a796}.point.split circle{fill:#7c9fbe}
    .map-side{display:grid;gap:10px}.mini{background:#f4f6f8;padding:14px;border-left:4px solid var(--line)}.mini b{display:block;font-size:22px}.mini span{font-size:12px;color:var(--muted)}
    .broker-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.broker-card{background:#fff;border:1px solid var(--line);padding:14px}.broker-card h3{margin:0 0 12px;font-size:18px}.broker-row{display:grid;grid-template-columns:92px 1fr 74px;align-items:center;gap:10px;padding:7px 0;border-top:1px solid #eef1f4}.broker-meter{height:8px;background:#edf1f4;border-radius:99px;overflow:hidden}.broker-meter i{display:block;height:100%;border-radius:99px}.broker-meter i.bull{background:var(--red)}.broker-meter i.bear{background:var(--green)}.broker-meter i.flat{background:#b4bcc7}
    .status{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.status-row{background:#fff;border:1px solid var(--line);padding:10px;display:flex;justify-content:space-between;gap:8px;align-items:center}.status-row span,.status-row em{font-size:12px;color:var(--muted);font-style:normal}.note{background:#fff8e6;border-left:5px solid var(--gold);padding:16px 18px;line-height:1.7}.foot{font-size:11px;color:var(--muted);border-top:1px solid var(--line);margin-top:30px;padding-top:14px}
    @media(max-width:860px){.top,.cards,.rank-grid,.map-wrap,.broker-grid,.status{grid-template-columns:1fr}.date{text-align:left}.legend{justify-content:flex-start}.rank-list{grid-template-columns:1fr}.section-title{grid-template-columns:1fr}.top h1{font-size:34px}}
    """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>外资席位持仓变化日报 {html.escape(str(date_label))}</title>
<style>{css}</style>
</head>
<body>
<main class="page">
  <header class="top">
    <div>
      <div class="eyebrow">Foreign Broker Positioning · Daily Flow Atlas</div>
      <h1>外资席位持仓变化日报</h1>
      <div class="sub">只跟踪高盛期货、摩根大通、瑞银期货；以手数变化衡量每日加多、加空，并与家人席位反向指标做共振校验。</div>
    </div>
    <div class="date">
      <b>{html.escape(str(date_label))}</b>
      <div class="sub">数据源：奇货可查 broker/position</div>
      <div class="legend"><span><i class="dot red"></i> 加多/偏多</span><span><i class="dot green"></i> 加空/偏空</span><span><i class="dot gold"></i> 共振</span></div>
    </div>
  </header>

  <section class="section">
    <div class="section-title"><em>01</em><h2>外资席位摘要</h2><span>单位：手；方向分数 = 加多 + 减空 - 减多 - 加空</span></div>
    <div class="cards">
      <div class="card"><div class="k">外资净方向</div><div class="v {direction_class(foreign_net)}">{signed(foreign_net)}</div><div class="s">{direction(foreign_net)}；外资合约行 {foreign_rows}</div></div>
      <div class="card"><div class="k">重点加多</div><div class="v red">{unsigned(foreign_add_long)}</div><div class="s">加多最多：{html.escape(top_bull_text)}</div></div>
      <div class="card"><div class="k">重点加空</div><div class="v green">{unsigned(foreign_add_short)}</div><div class="s">偏空最强：{html.escape(top_bear_text)}</div></div>
      <div class="card accent"><div class="k">家人反向共振</div><div class="v">{resonance_count} 个</div><div class="s">家人席位行 {family_rows}；家人与外资反向后同向计共振。</div></div>
    </div>
  </section>

  <section class="section">
    <div class="section-title"><em>02</em><h2>重点加多 / 加空品种</h2><span>外资三席位按品种汇总</span></div>
    <div class="rank-grid">
      <div><h3>加多排行</h3><div class="rank-list">{top_cards(foreign, "add_long", "外资加多")}</div></div>
      <div><h3>加空排行</h3><div class="rank-list">{top_cards(foreign, "add_short", "外资加空")}</div></div>
    </div>
  </section>

  <section class="section">
    <div class="section-title"><em>03</em><h2>加多 / 加空进度条</h2><span>只展示外资加仓活跃品种</span></div>
    <table>
      <thead><tr><th>品种</th><th class="num">加多</th><th class="num">加空</th><th>加多 / 加空比例</th><th class="num">净方向</th><th>方向强度</th><th>判断</th></tr></thead>
      <tbody>{rows_for_progress(foreign.rename(columns={"add_long":"foreign_add_long","add_short":"foreign_add_short"}).assign(flow_score=foreign["flow_score"]), 18)}</tbody>
    </table>
  </section>

  <section class="section">
    <div class="section-title"><em>04</em><h2>外资 × 家人反向共振地图</h2><span>右上为偏多共振，左下为偏空共振；气泡越大，当日变化越活跃</span></div>
    <div class="map-wrap">
      {scatter_svg(resonance)}
      <aside class="map-side">
        <div class="mini"><span>偏多共振</span><b class="red">{int(((resonance['is_resonance']) & (resonance['signal_score'] > 0)).sum()) if not resonance.empty else 0}</b></div>
        <div class="mini"><span>偏空共振</span><b class="green">{int(((resonance['is_resonance']) & (resonance['signal_score'] < 0)).sum()) if not resonance.empty else 0}</b></div>
        <div class="mini"><span>分歧品种</span><b>{int((~resonance['is_resonance']).sum()) if not resonance.empty else 0}</b></div>
        <div class="mini"><span>外资覆盖品种</span><b>{len(foreign)}</b></div>
      </aside>
    </div>
  </section>

  <section class="section">
    <div class="section-title"><em>05</em><h2>共振品种清单</h2><span>家人原始方向反向后，与外资方向一致</span></div>
    <table>
      <thead><tr><th>品种</th><th>共振方向</th><th class="num">外资净方向</th><th class="num">家人原始方向</th><th class="num">家人反向后</th><th class="num">共振强度</th><th>综合强度</th><th class="num">总变化</th></tr></thead>
      <tbody>{resonance_rows(resonance, 18)}</tbody>
    </table>
  </section>

  <section class="section">
    <div class="section-title"><em>06</em><h2>三家外资席位分拆</h2><span>每个席位最活跃品种</span></div>
    <div class="broker-grid">{''.join(broker_panel(broker_summary, b) for b in FOREIGN_BROKERS)}</div>
  </section>

  <section class="section">
    <div class="section-title"><em>07</em><h2>抓取状态</h2><span>不同席位可能披露日期不同，结论以此处日期为准</span></div>
    <div class="status">{status_cards}</div>
  </section>

  <section class="section note">
    <b>阅读口径：</b>外资加多、加空为三家外资席位按所有合约汇总后的正向多头变化、正向空头变化；减空会进入偏多方向分数，减多会进入偏空方向分数。家人席位按反向指标处理，因此“共振”指外资方向与家人反向后的方向一致。
  </section>

  <div class="foot">本报告仅为席位持仓数据整理，不构成投资建议。生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}。</div>
</main>
</body>
</html>"""


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows, fetch_status = fetch_rows()
    rows = add_flow_columns(rows)

    foreign = summarize_group(rows, "外资")
    family = summarize_group(rows, "家人")
    broker_summary = summarize_broker(rows)
    resonance = build_resonance(foreign, family)

    rows.to_csv(DATA_DIR / "contract_rows.csv", index=False, encoding="utf-8-sig")
    fetch_status.to_csv(DATA_DIR / "fetch_status.csv", index=False, encoding="utf-8-sig")
    foreign.to_csv(DATA_DIR / "foreign_variety_summary.csv", index=False, encoding="utf-8-sig")
    family.to_csv(DATA_DIR / "family_variety_summary.csv", index=False, encoding="utf-8-sig")
    broker_summary.to_csv(DATA_DIR / "foreign_broker_variety_summary.csv", index=False, encoding="utf-8-sig")
    resonance.to_csv(DATA_DIR / "foreign_family_resonance.csv", index=False, encoding="utf-8-sig")

    html_text = build_html(rows, fetch_status, foreign, family, broker_summary, resonance)
    (OUT_DIR / "report.html").write_text(html_text, encoding="utf-8")
    print(f"report: {OUT_DIR / 'report.html'}")
    print(f"foreign varieties: {len(foreign)}")
    print(f"resonance: {int(resonance['is_resonance'].sum()) if not resonance.empty else 0}")


if __name__ == "__main__":
    main()
