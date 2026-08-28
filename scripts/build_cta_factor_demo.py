from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "output" / "research_dashboard" / "data" / "snapshots"
OUTPUT_DIR = ROOT / "output" / "cta_factor_demo"
EXCLUDED = {"IC", "IF", "IH", "IM", "T", "TF", "TL", "TS", "CS", "AD", "PL", "RR", "CY", "OP", "RS"}
WEIGHTS = {"trend": 0.36, "seat": 0.315, "position": 0.135, "carry": 0.09, "option": 0.10}
LOSS_BROKERS = {"中信期货"}
RELATIVE_STRENGTH_SECTORS = {"家人品种", "有色金属", "油化工", "谷物饲料", "黑色系"}
DEFAULT_MACRO_PATH = ROOT.parent / "宏观经济-codex" / "site" / "public" / "data" / "latest.json"


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def signed_rank(value: float, peers: list[float]) -> float:
    nonzero = sorted(abs(item) for item in peers if item)
    if not value or not nonzero:
        return 0.0
    rank = sum(item <= abs(value) for item in nonzero) / len(nonzero)
    return math.copysign(rank, value)


def pct_change(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or not values[-periods - 1]:
        return None
    return values[-1] / values[-periods - 1] - 1


def realized_vol(values: list[float]) -> float | None:
    if len(values) < 6:
        return None
    returns = [values[index] / values[index - 1] - 1 for index in range(1, len(values)) if values[index - 1]]
    return statistics.pstdev(returns[-20:]) * math.sqrt(252) if len(returns) >= 5 else None


def carry_factor(fundamentals: dict) -> tuple[float | None, list[str]]:
    parts: list[float] = []
    evidence: list[str] = []
    basis = [row for row in fundamentals.get("basis", []) if row.get("basis_pct") is not None]
    if len(basis) >= 5:
        latest = float(basis[-1]["basis_pct"])
        median = statistics.median(float(row["basis_pct"]) for row in basis[-20:])
        parts.append(math.tanh((latest - median) / 5))
        evidence.append(f"基差率 {latest:.1f}%，20日中位 {median:.1f}%")
    receipts = [row for row in fundamentals.get("warehouseReceipt", []) if row.get("change") is not None]
    if receipts:
        changes = [float(row["change"]) for row in receipts[-5:]]
        scale = statistics.median(abs(float(row["change"])) for row in receipts[-20:] if float(row["change"])) if any(float(row["change"]) for row in receipts[-20:]) else 1.0
        parts.append(math.tanh(-sum(changes) / max(scale * 3, 1)))
        evidence.append(f"近5次仓单变化 {sum(changes):+,.0f}")
    return (sum(parts) / len(parts), evidence) if parts else (None, evidence)


def load_snapshots(report_date: str | None) -> list[dict]:
    files = sorted(SNAPSHOT_DIR.glob("*.json"))
    if report_date:
        files = [path for path in files if path.stem <= report_date]
    if not files:
        raise SystemExit("No workstation snapshots found")
    return [json.loads(path.read_text(encoding="utf-8")) for path in files]


def load_loss_rows(report_date: str) -> dict[str, dict[str, float]]:
    path = ROOT / "data" / f"qhkch_main_position_rows_{report_date}.csv"
    if not path.exists():
        return {}
    result: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("broker") not in LOSS_BROKERS:
                continue
            item = result.setdefault(row["symbol"], {"net": 0.0, "flow": 0.0})
            item["net"] += float(row.get("net_pos") or 0)
            item["flow"] += float(row.get("flow_score") or 0)
    return result


def load_option_rows(report_date: str) -> dict[str, dict[str, str]]:
    path = ROOT / "data" / f"openvlab_option_factors_{report_date}.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["symbol"]: row for row in csv.DictReader(handle) if row.get("status") == "OK"}


def option_factor(row: dict[str, str] | None) -> tuple[float | None, str]:
    if not row or not row.get("skew_percentile"):
        return None, "未提供期权截面"
    value = clamp((float(row["skew_percentile"]) - 50) / 50)
    evidence = (
        f"隐波 {float(row['implied_vol']):.2f}% / 实波 {float(row['realized_vol']):.2f}%；"
        f"偏度 {float(row['skew']):+.2f}；IV 分位 {float(row['iv_percentile']):.0f}；"
        f"偏度分位 {float(row['skew_percentile']):.0f}"
    )
    return value, evidence


def load_macro_context(report_date: str) -> dict:
    paths = [Path(os.environ["MACRO_WORKBENCH_DATA"])] if os.environ.get("MACRO_WORKBENCH_DATA") else []
    paths.append(DEFAULT_MACRO_PATH)
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if str(payload.get("asOf", ""))[:10].replace("-", "") == report_date:
            return payload
    return {}


def find_indicator(payload: object, indicator_id: str) -> dict:
    if isinstance(payload, dict):
        if payload.get("id") == indicator_id:
            return payload
        for value in payload.values():
            found = find_indicator(value, indicator_id)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_indicator(value, indicator_id)
            if found:
                return found
    return {}


def build_precious_metals_4d(rows: list[dict], macro: dict, report_date: str) -> dict | None:
    by_symbol = {row["symbol"]: row for row in rows}
    gold, silver = by_symbol.get("AU"), by_symbol.get("AG")
    if not gold or not silver:
        return None
    copper = by_symbol.get("CU")
    dxy, tips, pmi = (find_indicator(macro, key) for key in ("dxy", "tips10", "ismMfg"))

    def dimension(name: str, confirmed: bool | None, evidence: str, pending: bool = False) -> dict:
        status = "待确认" if pending or confirmed is None else "确认" if confirmed else "冲突"
        return {"name": name, "status": status, "evidence": evidence}

    gold_ret = gold.get("return20d")
    gold_sentiment = [gold["factors"].get(key) for key in ("position", "option") if gold["factors"].get(key) is not None]
    momentum_ok = gold_ret is not None and gold_ret > 0 and all(value >= 0 for value in gold_sentiment)
    momentum_pending = gold_ret is None or not gold_sentiment
    momentum_text = f"黄金20日 {gold_ret:+.1f}%" if gold_ret is not None else "黄金20日数据缺失"
    momentum_text += "；投机/边际 " + (" / ".join(f"{value:+.0f}" for value in gold_sentiment) if gold_sentiment else "缺失")

    dxy_change = dxy.get("pctChange")
    gold_day = gold.get("changePct")
    dxy_pending = dxy_change is None or gold_day is None
    dxy_ok = bool(gold_day > 0 and float(dxy_change) <= 0) if not dxy_pending else None
    if not dxy_pending and gold_day > 0 and float(dxy_change) > 0:
        dxy_pending = True
    dxy_text = "DXY或黄金日涨跌缺失" if dxy_change is None or gold_day is None else f"黄金 {gold_day:+.2f}% / DXY {float(dxy_change):+.2f}%"
    if dxy_pending and dxy_change is not None and gold_day is not None:
        dxy_text += "，同向状态需信用/流动性确认"

    pmi_value = float(pmi.get("displayValue")) if pmi.get("displayValue") not in (None, "") else None
    copper_ret = copper.get("return20d") if copper else None
    industrial_pending = pmi_value is None or copper_ret is None
    industrial_ok = bool(pmi_value >= 50 and copper_ret >= 0) if not industrial_pending else None
    industrial_text = f"ISM PMI {pmi_value:.1f} / 沪铜20日 {copper_ret:+.1f}%" if not industrial_pending else "ISM PMI或沪铜20日趋势缺失"

    tips_value, tips_previous = tips.get("value"), tips.get("previous")
    tips_pending = tips_value is None or tips_previous is None
    tips_ok = bool(float(tips_value) <= float(tips_previous)) if not tips_pending else None
    tips_text = f"10Y TIPS {float(tips_previous):.2f}% → {float(tips_value):.2f}%（{tips.get('dataDate', '日期缺失')}）" if not tips_pending else "10Y TIPS变化缺失"

    dimensions = [
        dimension("黄金动量 × 投机情绪", momentum_ok, momentum_text, momentum_pending),
        dimension("DXY × 黄金", dxy_ok, dxy_text, dxy_pending),
        dimension("工业 PMI 领先", industrial_ok, industrial_text, industrial_pending),
        dimension("实际利率", tips_ok, tips_text, tips_pending),
    ]
    relative20 = silver.get("return20d") - gold_ret if silver.get("return20d") is not None and gold_ret is not None else None
    relative_ok = relative20 is not None and relative20 > 0
    silver_position, silver_option = silver["factors"].get("position"), silver["factors"].get("option")
    flow_ok = silver_position is not None and silver_position >= 0 and silver_option is not None and silver_option > 0
    call_ready = all(item["status"] == "确认" for item in dimensions) and relative_ok and flow_ok
    blockers = [item["name"] for item in dimensions if item["status"] != "确认"]
    if not relative_ok:
        blockers.append("白银20日相对黄金转强")
    if not flow_ok:
        blockers.append("白银席位边际与期权偏度同向")
    missing = any(item["status"] == "待确认" for item in dimensions) or silver_position is None or silver_option is None or relative20 is None
    return {
        "asOf": macro.get("asOf") or report_date,
        "signal": "可考虑 Call 白银" if call_ready else "暂不 Call 白银" if any(item["status"] == "冲突" for item in dimensions) else "数据不足，继续观察" if missing else "暂不 Call 白银",
        "callSilver": call_ready,
        "relative20d": round(relative20, 1) if relative20 is not None else None,
        "dimensions": dimensions,
        "blockers": blockers,
    }


def cta_items(snapshot: dict) -> list[dict]:
    commodities = [item for item in snapshot.get("instruments", []) if item.get("symbol") not in EXCLUDED]
    indices = [
        {
            **item,
            "sector": "股指",
            "margin": {"perLot": 1},
            "resonance": {},
            "fundamentals": {},
            "ctaIndex": True,
        }
        for item in snapshot.get("stockIndices", [])
        if item.get("symbol") in {"IH", "IF", "IC", "IM"} and item.get("hasFuturesFlow")
    ]
    return commodities + indices


def seat_components(item: dict, loss_rows: dict[str, dict[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    if item.get("ctaIndex"):
        return item.get("stockComponents") or {}, item.get("flowComponents") or {}
    groups = item.get("groups") or {}
    loss = loss_rows.get(item["symbol"], {})
    family = groups.get("family") or {}
    stock = {
        "机构": float((groups.get("domestic") or {}).get("netPosition") or 0),
        "外资": float((groups.get("foreign") or {}).get("netPosition") or 0),
        "家人反向": -(float(family.get("netPosition") or 0) - float(loss.get("net") or 0)),
        "亏损机构反向": -float(loss.get("net") or 0),
    }
    flow = {
        "机构": float((groups.get("domestic") or {}).get("hands") or 0),
        "外资": float((groups.get("foreign") or {}).get("hands") or 0),
        "家人反向": -(float(family.get("hands") or 0) - float(loss.get("flow") or 0)),
        "亏损机构反向": -float(loss.get("flow") or 0),
    }
    return stock, flow


def component_text(parts: dict[str, float]) -> str:
    return " / ".join(f"{name} {value:+,.0f}" for name, value in parts.items())


def build_rows(snapshots: list[dict], loss_rows: dict[str, dict[str, float]], option_rows: dict[str, dict[str, str]], macro_context: dict | None = None) -> list[dict]:
    latest = snapshots[-1]
    history: dict[str, list[float]] = {}
    for snapshot in snapshots:
        for item in cta_items(snapshot):
            close = (item.get("quote") or {}).get("close")
            if close:
                history.setdefault(item["symbol"], []).append(float(close))

    instruments = cta_items(latest)
    components = {item["symbol"]: seat_components(item, loss_rows) for item in instruments}
    stock_amounts = {
        item["symbol"]: sum(components[item["symbol"]][0].values()) * float((item.get("margin") or {}).get("perLot") or 0)
        for item in instruments
    }
    flow_amounts = {
        item["symbol"]: sum(components[item["symbol"]][1].values()) * float((item.get("margin") or {}).get("perLot") or 0)
        for item in instruments
    }
    rows: list[dict] = []
    for item in instruments:
        symbol = item["symbol"]
        closes = history.get(symbol, [])
        ret5, ret20 = pct_change(closes, 5), pct_change(closes, 20)
        market_flow = item.get("marketFlow") or {}
        screenshot_ret10 = market_flow.get("return10d")
        screenshot_ret20 = market_flow.get("return20d")
        trend_parts = (
            [math.tanh(float(screenshot_ret10) / 6), math.tanh(float(screenshot_ret20) / 10)]
            if screenshot_ret10 is not None and screenshot_ret20 is not None
            else [value for value in (
                math.tanh(ret5 / 0.04) if ret5 is not None else None,
                math.tanh(ret20 / 0.10) if ret20 is not None else None,
            ) if value is not None]
        )
        trend = sum(trend_parts) / len(trend_parts) if trend_parts else None

        stock_parts, flow_parts = components[symbol]
        stock_amount = stock_amounts[symbol]
        flow_amount = flow_amounts[symbol]
        seat = signed_rank(stock_amount, list(stock_amounts.values()))
        if (item.get("resonance") or {}).get("triple"):
            seat = clamp(seat + math.copysign(0.12, stock_amount))

        change_pct = float((item.get("quote") or {}).get("changePct") or 0)
        position_change = sum(flow_parts.values())
        position = signed_rank(flow_amount, list(flow_amounts.values())) if flow_amount else None

        carry, carry_evidence = carry_factor(item.get("fundamentals") or {})
        option, option_evidence = option_factor(option_rows.get(symbol))
        factors = {"trend": trend, "seat": seat, "position": position, "carry": carry, "option": option}
        available = {name: value for name, value in factors.items() if value is not None}
        denominator = sum(WEIGHTS[name] for name in available)
        score = 100 * sum(WEIGHTS[name] * value for name, value in available.items()) / denominator if denominator else 0
        score = round(clamp(score, -100, 100))
        if score >= 35:
            signal = "强多"
        elif score >= 15:
            signal = "偏多"
        elif score <= -35:
            signal = "强空"
        elif score <= -15:
            signal = "偏空"
        else:
            signal = "中性"

        vol = realized_vol(closes)
        rows.append({
            "symbol": symbol,
            "variety": item.get("variety") or symbol,
            "sector": item.get("sector") or "未分类",
            "score": score,
            "signal": signal,
            "coverage": round(100 * denominator / sum(WEIGHTS.values())),
            "close": (item.get("quote") or {}).get("close"),
            "changePct": change_pct,
            "amountSignal": flow_amount,
            "positionChange": position_change,
            "volatility": round(vol * 100, 1) if vol is not None else None,
            "return20d": float(screenshot_ret20) if screenshot_ret20 is not None else round(ret20 * 100, 1) if ret20 is not None else None,
            "factors": {name: None if value is None else round(value * 100) for name, value in factors.items()},
            "evidence": {
                "trend": (
                    f"10日 {float(screenshot_ret10):+.1f}% / 20日 {float(screenshot_ret20):+.1f}%（同花顺截图）"
                    if screenshot_ret10 is not None and screenshot_ret20 is not None
                    else f"5日 {ret5 * 100:+.1f}% / 20日 {ret20 * 100:+.1f}%" if ret5 is not None and ret20 is not None else "历史不足"
                ),
                "seat": f"合成存量 {stock_amount / 1e8:+.2f} 亿；{component_text(stock_parts)}",
                "position": f"合成边际 {flow_amount / 1e8:+.2f} 亿；{component_text(flow_parts)}" if position is not None else "当日席位增减仓不足",
                "carry": "；".join(carry_evidence) or "基差/仓单不足",
                "option": option_evidence,
            },
        })
    framework = build_precious_metals_4d(rows, macro_context if macro_context is not None else load_macro_context(str(latest.get("date", ""))), str(latest.get("date", "")))
    if framework:
        for row in rows:
            if row["symbol"] in {"AU", "AG"}:
                row["metal4d"] = framework
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def render_html(report_date: str, rows: list[dict]) -> str:
    for sector in RELATIVE_STRENGTH_SECTORS:
        peers = [row for row in rows if row["sector"] == sector]
        if not peers:
            continue
        max(peers, key=lambda row: row["score"])["relative_strength"] = "板块最强"
        if len(peers) > 1:
            min(peers, key=lambda row: row["score"])["relative_strength"] = "板块最弱"
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    sectors = sorted({row["sector"] for row in rows})
    options = "".join(f'<option value="{escape(sector)}">{escape(sector)}</option>' for sector in sectors)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>CTA 因子评分 Demo · {report_date}</title>
<style>
:root{{--bg:#eef1f4;--ink:#17212b;--muted:#6d7885;--line:#cfd7df;--paper:#fff;--bull:#c9445a;--bear:#008271;--gold:#b48a2c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 "Microsoft YaHei",sans-serif}}button,select,input{{font:inherit}}
header{{padding:24px max(24px,calc((100vw - 1180px)/2));background:#14202b;color:#fff;border-bottom:4px solid var(--gold)}}
.eyebrow{{color:#d5b45b;font:12px Georgia,serif}}h1{{margin:6px 0 2px;font-size:30px}}header p{{margin:0;color:#aab6c2}}
main{{max-width:1180px;margin:auto;padding:22px}}.toolbar{{display:grid;grid-template-columns:1fr 220px 190px;gap:10px;margin-bottom:16px}}
input,select{{width:100%;min-height:42px;padding:8px 12px;border:1px solid var(--line);background:#fff;border-radius:2px}}
.summary{{display:grid;grid-template-columns:2fr repeat(4,1fr);border:1px solid var(--line);background:var(--paper)}}.summary>div{{padding:17px;border-right:1px solid var(--line)}}.summary>div:last-child{{border:0}}
.summary strong{{display:block;margin-top:4px;font-size:24px}}.bull{{color:var(--bull)}}.bear{{color:var(--bear)}}.muted{{color:var(--muted)}}
.layout{{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(340px,.85fr);gap:16px;margin-top:16px}}
.panel{{background:var(--paper);border:1px solid var(--line)}}.panel h2{{margin:0;padding:15px 17px;border-bottom:2px solid var(--ink);font-size:18px}}
.rank-head,.rank-row{{display:grid;grid-template-columns:46px minmax(130px,1fr) 90px 86px 78px;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #e2e7ec}}
.rank-head{{color:var(--muted);font-size:12px;background:#f5f7f8}}.rank-row{{cursor:pointer}}.rank-row:hover,.rank-row.active{{background:#f3f6f8}}.rank-row strong{{font-size:15px}}
.relative-badge{{display:inline-block;margin-left:6px;padding:1px 4px;border:1px solid currentColor;border-radius:2px;font-size:10px;font-weight:700;vertical-align:2px;white-space:nowrap}}
.score{{font-size:22px;font-weight:800;text-align:right;font-variant-numeric:tabular-nums}}.bar{{height:6px;background:#e7ecef}}.bar i{{display:block;height:100%}}
.detail{{position:sticky;top:12px;align-self:start}}.detail-body{{padding:17px}}.detail-title{{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--line);padding-bottom:14px}}
.detail-title h3{{margin:0;font-size:25px}}.detail-title b{{font-size:34px}}.factor{{padding:13px 0;border-bottom:1px solid #e2e7ec}}.factor-top{{display:flex;justify-content:space-between;font-weight:700}}
.factor p{{margin:5px 0 0;color:var(--muted);font-size:12px}}.factor .bar{{margin-top:8px;position:relative}}.factor .bar:after{{content:"";position:absolute;left:50%;top:-3px;height:12px;border-left:1px solid #7f8a94}}
.factor .bar i{{position:absolute;max-width:50%}}.source{{margin-top:16px;padding:14px;background:#f4f6f7;color:var(--muted);font-size:12px}}.source b{{color:var(--ink)}}
footer{{max-width:1180px;margin:0 auto 24px;padding:0 22px;color:var(--muted);font-size:12px}}
@media(max-width:820px){{.toolbar{{grid-template-columns:1fr 1fr}}.toolbar input{{grid-column:1/-1}}.summary{{grid-template-columns:1fr 1fr}}.summary>div{{border-bottom:1px solid var(--line)}}.layout{{grid-template-columns:1fr}}.detail{{position:static}}}}
@media(max-width:520px){{main{{padding:12px}}header{{padding:20px 14px}}h1{{font-size:24px}}.rank-head,.rank-row{{grid-template-columns:34px minmax(110px,1fr) 66px 62px}}.rank-head span:nth-child(4),.rank-row .coverage{{display:none}}.summary strong{{font-size:20px}}}}
</style></head><body>
<header><div class="eyebrow">QUANT RESEARCH · EXPLAINABLE V1</div><h1>CTA 因子评分 Demo</h1><p>{report_date[:4]}-{report_date[4:6]}-{report_date[6:]} · 同口径结果已并入研究工作站</p></header>
<main><div class="toolbar"><input id="search" placeholder="筛选品种或代码"><select id="sector"><option value="">全部板块</option>{options}</select><select id="direction"><option value="">全部方向</option><option>强多</option><option>偏多</option><option>中性</option><option>偏空</option><option>强空</option></select></div>
<section class="summary"><div><span class="muted">市场方向</span><strong id="marketRead">—</strong></div><div><span class="muted">偏多</span><strong class="bull" id="bullCount">0</strong></div><div><span class="muted">中性</span><strong id="flatCount">0</strong></div><div><span class="muted">偏空</span><strong class="bear" id="bearCount">0</strong></div><div><span class="muted">平均覆盖</span><strong id="coverage">0%</strong></div></section>
<div class="layout"><section class="panel"><h2>CTA 截面评分</h2><div class="rank-head"><span>排名</span><span>品种</span><span>分数</span><span>覆盖</span><span>信号</span></div><div id="rank"></div></section>
<aside class="panel detail"><h2>因子拆解</h2><div class="detail-body" id="detail"></div></aside></div></main>
<footer>Demo 评分不是回测后的交易策略。奇货可查提供席位/保证金事实；价格、基差与仓单沿用工作站已核验底表；同花顺与 OpenVLab 截图属于二级证据。隐波分位只作拥挤风险证据，偏度分位决定方向，缺失品种不扣分。</footer>
<script>const DATA={payload};
const labels={{trend:'量价趋势',seat:'席位存量',position:'席位边际',carry:'基差与仓单',option:'期权偏度'}};
const rank=document.querySelector('#rank'),detail=document.querySelector('#detail');let selected=DATA[0]?.symbol;
function tone(v){{return v>0?'bull':v<0?'bear':''}}function fmt(v,d=0){{return Number(v).toLocaleString('zh-CN',{{maximumFractionDigits:d}})}}
function bar(v){{if(v==null)return '<div class="bar"></div>';const left=v<0?50+v/2:50,width=Math.abs(v)/2;return `<div class="bar"><i style="left:${{left}}%;width:${{width}}%;background:${{v>=0?'var(--bull)':'var(--bear)'}}"></i></div>`}}
function showDetail(row){{if(!row)return;selected=row.symbol;document.querySelectorAll('.rank-row').forEach(el=>el.classList.toggle('active',el.dataset.symbol===selected));detail.innerHTML=`<div class="detail-title"><div><h3>${{row.variety}} <small>${{row.symbol}}</small></h3><span class="muted">${{row.sector}} · 年化波动 ${{row.volatility??'—'}}%</span></div><b class="${{tone(row.score)}}">${{row.score>0?'+':''}}${{row.score}}</b></div>${{Object.entries(labels).map(([key,label])=>`<div class="factor"><div class="factor-top"><span>${{label}}</span><span class="${{tone(row.factors[key])}}">${{row.factors[key]==null?'未覆盖':(row.factors[key]>0?'+':'')+row.factors[key]}}</span></div>${{bar(row.factors[key])}}<p>${{row.evidence[key]}}</p></div>`).join('')}}<div class="source"><b>解释边界</b><br>可用因子覆盖 ${{row.coverage}}%。分数按可用权重重算，缺失不等于中性；波动率只作风险标签，不决定方向。</div>`}}
function render(){{const q=document.querySelector('#search').value.trim().toLowerCase(),sector=document.querySelector('#sector').value,direction=document.querySelector('#direction').value;const rows=DATA.filter(r=>(!q||(r.variety+r.symbol).toLowerCase().includes(q))&&(!sector||r.sector===sector)&&(!direction||r.signal===direction));rank.innerHTML=rows.map((r,i)=>`<div class="rank-row ${{r.symbol===selected?'active':''}}" data-symbol="${{r.symbol}}"><span>${{i+1}}</span><span><strong>${{r.variety}}</strong>${{r.relative_strength?`<em class="relative-badge ${{r.relative_strength==='板块最强'?'bull':'bear'}}">${{r.relative_strength}}</em>`:''}} <small>${{r.symbol}}</small>${{bar(r.score)}}</span><span class="score ${{tone(r.score)}}">${{r.score>0?'+':''}}${{r.score}}</span><span class="coverage">${{r.coverage}}%</span><span class="${{tone(r.score)}}">${{r.signal}}</span></div>`).join('')||'<p class="muted" style="padding:20px">没有匹配品种</p>';document.querySelectorAll('.rank-row').forEach(el=>el.onclick=()=>showDetail(DATA.find(r=>r.symbol===el.dataset.symbol)));const bull=rows.filter(r=>r.score>=15).length,bear=rows.filter(r=>r.score<=-15).length,flat=rows.length-bull-bear;bullCount.textContent=bull;bearCount.textContent=bear;flatCount.textContent=flat;coverage.textContent=(rows.length?Math.round(rows.reduce((s,r)=>s+r.coverage,0)/rows.length):0)+'%';marketRead.textContent=bull>bear?'多头占优':bear>bull?'空头占优':'多空均衡';marketRead.className=bull>bear?'bull':bear>bull?'bear':'';showDetail(rows.find(r=>r.symbol===selected)||rows[0])}}
document.querySelectorAll('.toolbar input,.toolbar select').forEach(el=>el.addEventListener('input',render));render();</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYYMMDD; defaults to latest snapshot")
    args = parser.parse_args()
    snapshots = load_snapshots(args.date)
    report_date = snapshots[-1]["date"]
    rows = build_rows(snapshots, load_loss_rows(report_date), load_option_rows(report_date))
    assert rows and all(-100 <= row["score"] <= 100 for row in rows)
    assert not ({row["symbol"] for row in rows} & (EXCLUDED - {"IC", "IF", "IH", "IM"}))
    assert {row["symbol"] for row in rows if row["sector"] == "股指"} == {"IC", "IF", "IH", "IM"}
    assert all(row["sector"] == "股指" or "亏损机构反向" in row["evidence"]["seat"] for row in rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / "index.html"
    target.write_text(render_html(report_date, rows), encoding="utf-8")
    marked = [row for row in rows if row.get("relative_strength")]
    assert len(marked) == 2 * len(RELATIVE_STRENGTH_SECTORS)
    assert not any(row.get("relative_strength") for row in rows if row["sector"] not in RELATIVE_STRENGTH_SECTORS)
    assert target.stat().st_size > 20_000 and f"CTA 因子评分 Demo" in target.read_text(encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
