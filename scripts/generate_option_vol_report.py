from __future__ import annotations

import csv
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path.cwd()
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
OUT_DIR = ROOT / "output" / f"option_vol_report_{RUN_DATE}"
DATA_DIR = OUT_DIR / "data"

OPENVLAB_MARKET = "https://www.openvlab.cn/market"
OPENVLAB_LIGHT_BASE = "https://www.openvlab.cn/chart/light/"
OPENVLAB_VOL_BASE = "https://www.openvlab.cn/volatility/analysis/"


@dataclass(frozen=True)
class OptionItem:
    code: str
    name: str
    symbol: str
    display: str
    month: str
    cp: str
    strike: int

    @property
    def underlying_code(self) -> str:
        return f"{self.symbol}20{self.month}"

    @property
    def chart_url(self) -> str:
        return f"{OPENVLAB_LIGHT_BASE}{self.underlying_code}"

    @property
    def vol_url(self) -> str:
        return f"{OPENVLAB_VOL_BASE}{self.symbol}"


WATCHLIST = [
    OptionItem("lc2609-C-160000", "碳酸锂2609购160000", "LC", "碳酸锂", "2609", "C", 160000),
    OptionItem("ag2608C15000", "沪银2608购15000", "AG", "沪银", "2608", "C", 15000),
    OptionItem("TA2608C5800", "PTA2608购5800", "TA", "PTA", "2608", "C", 5800),
    OptionItem("eb2608-C-7500", "苯乙烯2608购7500", "EB", "苯乙烯", "2608", "C", 7500),
    OptionItem("jm2608-C-1300", "焦煤2608购1300", "JM", "焦煤", "2608", "C", 1300),
    OptionItem("lh2609-P-12000", "生猪2609沽12000", "LH", "生猪", "2609", "P", 12000),
    OptionItem("lh2609-C-13000", "生猪2609购13000", "LH", "生猪", "2609", "C", 13000),
    OptionItem("MA2608P2400", "甲醇2608沽2400", "MA", "甲醇", "2608", "P", 2400),
    OptionItem("ag2608P13000", "沪银2608沽13000", "AG", "沪银", "2608", "P", 13000),
    OptionItem("sc2608P450", "原油2608沽450", "SC", "原油", "2608", "P", 450),
    OptionItem("ru2609P17000", "橡胶2609沽17000", "RU", "橡胶", "2609", "P", 17000),
    OptionItem("au2608P880", "沪金2608沽880", "AU", "沪金", "2608", "P", 880),
    OptionItem("fu2608P3000", "燃油2608沽3000", "FU", "燃油", "2608", "P", 3000),
    OptionItem("fu2608C3000", "燃油2608购3000", "FU", "燃油", "2608", "C", 3000),
    OptionItem("ru2609C17000", "橡胶2609购17000", "RU", "橡胶", "2609", "C", 17000),
]

# User screenshot sample for the current demo. Live values replace it when a public endpoint is available.
SCREENSHOT_SAMPLE = {
    ("AG", "2608"): {
        "implied_vol": 53.31,
        "realized_vol": 57.04,
        "skew": -2.25,
        "iv_percentile": 61.0,
        "skew_percentile": 3.0,
        "source_note": "用户截图样例，待OpenVLab历史接口确认",
    }
}


def fetch_text(url: str) -> tuple[str, str]:
    try:
        req = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/json",
                "Accept-Encoding": "identity",
            },
        )
        with urlopen(req, timeout=25) as resp:
            return resp.read().decode("utf-8", "replace"), "OK"
    except Exception as exc:
        return "", f"FETCH_FAILED: {type(exc).__name__}: {exc}"


def extract_metric(text: str, labels: list[str]) -> float | None:
    compact = re.sub(r"\s+", "", text)
    for label in labels:
        match = re.search(re.escape(label) + r"[^0-9+\-]{0,20}([-+]?\d+(?:\.\d+)?)", compact)
        if match:
            return float(match.group(1))
    return None


def page_probe(item: OptionItem) -> dict[str, object]:
    chart_html, chart_status = fetch_text(item.chart_url)
    vol_html, vol_status = fetch_text(item.vol_url)
    combined = chart_html + "\n" + vol_html
    has_next_data = "__NEXT_DATA__" in combined
    script_count = combined.count("/_next/static/")
    metrics = {
        "implied_vol": extract_metric(combined, ["隐波", "平均隐波"]),
        "realized_vol": extract_metric(combined, ["实波", "实际波动率"]),
        "skew": extract_metric(combined, ["偏度"]),
        "iv_percentile": extract_metric(combined, ["隐波%", "隐波百分位"]),
        "skew_percentile": extract_metric(combined, ["偏度%", "偏度百分位"]),
    }
    source_note = "OpenVLab页面可访问；核心指标由前端动态加载，静态HTML未解析到完整历史序列"
    if any(value is not None for value in metrics.values()):
        source_note = "OpenVLab静态HTML解析"
    sample = SCREENSHOT_SAMPLE.get((item.symbol, item.month))
    if sample and not any(value is not None for value in metrics.values()):
        metrics.update({k: v for k, v in sample.items() if k != "source_note"})
        source_note = sample["source_note"]
    return {
        **metrics,
        "chart_status": chart_status,
        "vol_status": vol_status,
        "has_next_data": has_next_data,
        "script_count": script_count,
        "source_note": source_note,
    }


def fmt_num(value: object, suffix: str = "") -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.2f}{suffix}"
    return html.escape(str(value))


def bar(value: object, max_abs: float, cls: str) -> str:
    if not isinstance(value, (int, float)) or max_abs <= 0:
        return '<span class="bar muted"><i style="width:0%"></i></span>'
    width = min(100, abs(value) / max_abs * 100)
    return f'<span class="bar {cls}"><i style="width:{width:.1f}%"></i></span>'


def signal(row: dict[str, object]) -> tuple[str, str]:
    iv = row.get("implied_vol")
    rv = row.get("realized_vol")
    skew = row.get("skew")
    if isinstance(iv, (int, float)) and isinstance(rv, (int, float)):
        if iv > rv:
            return "隐波溢价", "red"
        if iv < rv:
            return "隐波折价", "green"
    if isinstance(skew, (int, float)) and abs(skew) >= 2:
        return "偏度极端", "gold"
    return "待确认", "gray"


def build_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    market_html, market_status = fetch_text(OPENVLAB_MARKET)
    fetch_status = [{
        "url": OPENVLAB_MARKET,
        "status": market_status,
        "bytes": len(market_html),
        "has_next_data": "__NEXT_DATA__" in market_html,
        "script_count": market_html.count("/_next/static/"),
    }]
    rows: list[dict[str, object]] = []
    for item in WATCHLIST:
        probe = page_probe(item)
        sig_text, sig_cls = signal(probe)
        rows.append({
            "code": item.code,
            "name": item.name,
            "symbol": item.symbol,
            "display": item.display,
            "month": item.month,
            "cp": "购" if item.cp.upper() == "C" else "沽",
            "strike": item.strike,
            "underlying": item.underlying_code,
            "chart_url": item.chart_url,
            "vol_url": item.vol_url,
            "signal": sig_text,
            "signal_class": sig_cls,
            **probe,
        })
        fetch_status.append({
            "url": item.chart_url,
            "status": probe["chart_status"],
            "bytes": "",
            "has_next_data": probe["has_next_data"],
            "script_count": probe["script_count"],
        })
        fetch_status.append({
            "url": item.vol_url,
            "status": probe["vol_status"],
            "bytes": "",
            "has_next_data": probe["has_next_data"],
            "script_count": probe["script_count"],
        })
    return rows, fetch_status


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def render_html(rows: list[dict[str, object]], fetch_status: list[dict[str, object]]) -> str:
    parsed_rows = [r for r in rows if any(isinstance(r.get(k), (int, float)) for k in ["implied_vol", "realized_vol", "skew"])]
    iv_values = [r["implied_vol"] for r in rows if isinstance(r.get("implied_vol"), (int, float))]
    rv_values = [r["realized_vol"] for r in rows if isinstance(r.get("realized_vol"), (int, float))]
    skew_values = [r["skew"] for r in rows if isinstance(r.get("skew"), (int, float))]
    max_vol = max([1.0] + [float(v) for v in iv_values + rv_values])
    max_skew = max([1.0] + [abs(float(v)) for v in skew_values])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cards = "".join([
        f'<div class="metric"><b>{len(rows)}</b><span>观察期权合约</span></div>',
        f'<div class="metric"><b>{len(parsed_rows)}</b><span>已落地指标行</span></div>',
        f'<div class="metric"><b>{fmt_num(max(iv_values) if iv_values else None, "%")}</b><span>最高隐波</span></div>',
        '<div class="metric warm"><b>5日</b><span>历史序列待接入</span></div>',
    ])

    rows_html = []
    for row in rows:
        sig_cls = row["signal_class"]
        rows_html.append(f"""
        <tr>
          <td><strong>{html.escape(str(row['display']))}</strong><em>{html.escape(str(row['code']))}</em></td>
          <td>{html.escape(str(row['cp']))}<em>{row['month']} / {row['strike']}</em></td>
          <td><span class="pill {sig_cls}">{html.escape(str(row['signal']))}</span></td>
          <td><span class="num red">{fmt_num(row.get('implied_vol'), '%')}</span>{bar(row.get('implied_vol'), max_vol, 'red')}</td>
          <td><span class="num blue">{fmt_num(row.get('realized_vol'), '%')}</span>{bar(row.get('realized_vol'), max_vol, 'blue')}</td>
          <td><span class="num {'red' if isinstance(row.get('skew'), (int, float)) and row.get('skew') > 0 else 'green'}">{fmt_num(row.get('skew'))}</span>{bar(row.get('skew'), max_skew, 'green')}</td>
          <td>{fmt_num(row.get('iv_percentile'), '%')}<em>偏度% {fmt_num(row.get('skew_percentile'), '%')}</em></td>
          <td><a href="{html.escape(str(row['chart_url']))}">行情</a> · <a href="{html.escape(str(row['vol_url']))}">波动率</a><em>{html.escape(str(row['source_note']))}</em></td>
        </tr>
        """)

    status_html = "".join(
        f'<div class="status-row"><span>{html.escape(str(item["url"]))}</span><b>{html.escape(str(item["status"]))}</b></div>'
        for item in fetch_status[:18]
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>期权波动率观察日报 Demo {RUN_DATE}</title>
  <style>
    :root {{
      --bg:#f4f6f8; --paper:#fff; --ink:#17212f; --muted:#667085; --line:#d8dee8;
      --red:#c94b62; --green:#007f6e; --blue:#5077a2; --gold:#b8862b; --soft:#f7efe0;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.55 Arial, "Microsoft YaHei", sans-serif; }}
    .page {{ width:min(1180px, calc(100vw - 40px)); margin:0 auto; padding:42px 0 54px; }}
    header {{ display:grid; grid-template-columns:1fr auto; gap:24px; align-items:end; border-bottom:3px solid #222; padding-bottom:22px; }}
    .eyebrow {{ color:var(--gold); font-size:12px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
    h1 {{ margin:6px 0 4px; font-size:42px; line-height:1.05; letter-spacing:0; }}
    .sub {{ color:var(--muted); max-width:760px; }}
    .date {{ text-align:right; font-size:26px; font-weight:800; }}
    .grid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; margin:26px 0 30px; }}
    .metric {{ background:var(--paper); border:1px solid var(--line); border-radius:8px; padding:18px 20px; box-shadow:0 8px 20px rgba(20,30,45,.05); }}
    .metric b {{ display:block; font-size:30px; color:var(--red); }}
    .metric span {{ color:var(--muted); }}
    .metric.warm {{ background:var(--soft); border-color:#dfc790; }}
    .section {{ margin-top:28px; }}
    .title {{ display:flex; align-items:end; justify-content:space-between; border-bottom:3px solid #222; padding-bottom:10px; margin-bottom:14px; }}
    .title h2 {{ margin:0; font-size:26px; }}
    .title small {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; background:var(--paper); border:1px solid var(--line); }}
    th {{ text-align:left; padding:12px 14px; color:#475467; font-size:12px; border-bottom:1px solid var(--line); background:#fbfcfd; }}
    td {{ padding:14px; border-bottom:1px solid #eef1f5; vertical-align:middle; }}
    td em {{ display:block; margin-top:3px; font-style:normal; color:var(--muted); font-size:12px; }}
    a {{ color:var(--blue); text-decoration:none; font-weight:700; }}
    .num {{ display:inline-block; min-width:70px; font-weight:800; font-size:18px; }}
    .red {{ color:var(--red); }} .green {{ color:var(--green); }} .blue {{ color:var(--blue); }}
    .bar {{ display:inline-block; width:110px; height:8px; background:#edf1f4; border-radius:99px; overflow:hidden; vertical-align:middle; margin-left:8px; }}
    .bar i {{ display:block; height:100%; border-radius:99px; }}
    .bar.red i {{ background:var(--red); }} .bar.green i {{ background:var(--green); }} .bar.blue i {{ background:var(--blue); }}
    .pill {{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:800; font-size:12px; background:#edf1f4; }}
    .pill.red {{ color:var(--red); background:#f8e7eb; }} .pill.green {{ color:var(--green); background:#dff3ef; }}
    .pill.gold {{ color:#8f641d; background:#f6ead0; }} .pill.gray {{ color:#667085; }}
    .note {{ background:#fff8e8; border-left:4px solid var(--gold); padding:16px 18px; margin-top:18px; color:#3d3d3d; }}
    .status {{ display:grid; grid-template-columns:1fr; gap:8px; }}
    .status-row {{ display:grid; grid-template-columns:1fr auto; gap:16px; padding:10px 12px; background:#fff; border:1px solid var(--line); }}
    .status-row span {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--muted); }}
    .status-row b {{ font-size:12px; }}
    footer {{ margin-top:32px; color:var(--muted); font-size:12px; border-top:1px solid var(--line); padding-top:16px; }}
    @media (max-width: 860px) {{ .grid {{ grid-template-columns:1fr 1fr; }} table {{ font-size:12px; }} .bar {{ width:70px; }} header {{ grid-template-columns:1fr; }} .date {{ text-align:left; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <div class="eyebrow">OPTIONS VOLATILITY WATCH · DEMO</div>
        <h1>期权波动率观察日报</h1>
        <div class="sub">观察用户截图中的期权合约，重点看近 5 日实波、隐含波动率、偏度与百分位。当前版本先验证 OpenVLab 页面可访问性与报告视觉结构，历史序列接口接入后自动补齐。</div>
      </div>
      <div class="date">{RUN_DATE[:4]}.{RUN_DATE[4:6]}.{RUN_DATE[6:]}</div>
    </header>
    <section class="grid">{cards}</section>
    <section class="section">
      <div class="title"><h2>01 关注期权波动率快照</h2><small>红=看多/上涨语境；绿=看空/下跌语境；本表不构成投资建议</small></div>
      <table>
        <thead><tr><th>品种/代码</th><th>方向/行权</th><th>波动信号</th><th>隐波</th><th>实波</th><th>偏度</th><th>百分位</th><th>来源</th></tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
      <div class="note">5 日分析口径建议：隐波上行且实波跟随，代表波动交易正在兑现；隐波上行但实波不动，优先视为预期升温或权利金偏贵；偏度极端时，重点看对应方向期权是否已拥挤。</div>
    </section>
    <section class="section">
      <div class="title"><h2>02 OpenVLab 抓取状态</h2><small>前端动态数据未伪装为已确认历史数据</small></div>
      <div class="status">{status_html}</div>
    </section>
    <footer>生成时间：{now}。数据来源尝试：OpenVLab market、行情 light 页面、波动率 analysis 页面；截图样例仅用于 demo 结构，不作为独立交易依据。</footer>
  </main>
</body>
</html>"""


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows, fetch_status = build_rows()
    write_csv(DATA_DIR / "option_watchlist_snapshot.csv", rows)
    write_csv(DATA_DIR / "openvlab_fetch_status.csv", fetch_status)
    (DATA_DIR / "option_watchlist.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    html_text = render_html(rows, fetch_status)
    (OUT_DIR / "report.html").write_text(html_text, encoding="utf-8")
    parsed = sum(1 for row in rows if any(isinstance(row.get(k), (int, float)) for k in ["implied_vol", "realized_vol", "skew"]))
    print(f"option report: {OUT_DIR / 'report.html'}; rows={len(rows)} parsed={parsed}")


if __name__ == "__main__":
    main()
