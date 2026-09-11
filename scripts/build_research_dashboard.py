from __future__ import annotations

import csv
import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .build_cta_factor_demo import build_rows as build_cta_rows
    from .build_cta_factor_demo import load_loss_rows, load_option_rows
except ImportError:
    from build_cta_factor_demo import build_rows as build_cta_rows
    from build_cta_factor_demo import load_loss_rows, load_option_rows


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "output"
SOURCE_DIR = ROOT / "web" / "research_dashboard"
TARGET_DIR = OUTPUT_ROOT / "research_dashboard"
SNAPSHOT_DIR = TARGET_DIR / "data" / "snapshots"
FUNDAMENTAL_SOURCE_CONFIG = ROOT / "config" / "fundamental_sources.json"
DATE_RE = re.compile(r"(\d{8})$")
EXCLUDED_SYMBOLS = {
    "IC", "IF", "IH", "IM", "T", "TF", "TL", "TS", "CS",
    "AD", "PL", "RR", "CY", "OP", "RS",
}
SECTOR_OVERRIDES = {
    "LU": "油化工", "PR": "油化工", "NR": "农副软商",
    "PS": "家人品种", "SP": "家人品种",
}
ANALYSIS_SECTORS = {"贵金属", "有色金属", "家人品种", "黑色系", "油化工", "谷物饲料", "油脂油料", "农副软商"}
WATCHLIST_SYMBOLS = {"AU", "AG", "SN", "LC", "FU", "JM", "I", "FG", "SA", "AO", "SH", "M", "JD", "LH", "P", "RU"}
ACTIVE_TEMPERATURES = {"温", "热", "沸", "凉", "寒", "冻"}
BEIJING = ZoneInfo("Asia/Shanghai")


def broker_display_group(broker: str, group: str) -> str:
    if broker == "中信期货":
        return "亏损机构（特殊）"
    return {"内资": "机构", "外资": "外资", "家人": "家人"}.get(group, group)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def fundamental_source_plans() -> dict[str, dict[str, object]]:
    payload = read_json(FUNDAMENTAL_SOURCE_CONFIG)
    profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
    symbols = payload.get("symbols", {}) if isinstance(payload, dict) else {}
    if not isinstance(profiles, dict) or not isinstance(symbols, dict):
        return {}
    return {
        str(symbol).upper(): dict(profiles.get(profile_name, {}))
        for symbol, profile_name in symbols.items()
        if isinstance(profiles.get(profile_name), dict)
    }


def fundamental_fact_index(
    rows: list[dict[str, str]], report_date: str
) -> dict[str, list[dict[str, object]]]:
    allowed_dimensions = {"supply", "demand", "cost", "inventory"}
    report_iso = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    latest: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        dimension = row.get("dimension", "").strip().lower()
        metric = row.get("metric", "").strip()
        source_date = row.get("source_date", "").strip()
        if (
            not symbol
            or dimension not in allowed_dimensions
            or not metric
            or row.get("status", "").strip().upper() != "OK"
            or not source_date
            or source_date > report_iso
        ):
            continue
        try:
            value = float(row.get("value", ""))
        except (TypeError, ValueError):
            continue
        fact = {
            "dimension": dimension,
            "metric": metric,
            "value": value,
            "unit": row.get("unit", "").strip(),
            "sourceDate": source_date,
            "frequency": row.get("frequency", "").strip(),
            "source": row.get("source", "Mysteel").strip() or "Mysteel",
            "sourceUrl": row.get("source_url", "").strip(),
        }
        key = (symbol, dimension, metric)
        previous = latest.get(key)
        if previous is None or str(previous["sourceDate"]) < source_date:
            latest[key] = fact
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (symbol, _, _), fact in latest.items():
        grouped[symbol].append(fact)
    for facts in grouped.values():
        facts.sort(key=lambda item: (str(item["dimension"]), str(item["metric"])))
    return dict(grouped)


def latest_dated_file(pattern: str, report_date: str) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in (ROOT / "data").glob(pattern):
        match = re.search(r"(\d{8})", path.stem)
        if match and match.group(1) <= report_date:
            candidates.append((match.group(1), path))
    return max(candidates, default=("", None), key=lambda item: item[0])[1]


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def optional_number(value: object) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def flag(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def discover_dates(prefix: str) -> set[str]:
    dates: set[str] = set()
    for path in OUTPUT_ROOT.glob(f"{prefix}_*"):
        match = DATE_RE.search(path.name)
        if match:
            dates.add(match.group(1))
    return dates


def row_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("symbol", "").upper(): row for row in rows if row.get("symbol")}


def trend_index(rows: list[dict[str, str]], report_date: str) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    iso_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    for row in rows:
        symbol = row.get("symbol", "").upper()
        if not symbol:
            continue
        source_date = row.get("snapshot_date", "")
        temperature = row.get("temperature", "")
        stage = row.get("trend_stage", "") or row.get("trend_phase_curr", "")
        indexed[symbol] = {
            "temperature": temperature,
            "strength": number(row.get("strength")),
            "rank": number(row.get("trend_rank")),
            "stage": stage,
            "note": row.get("note", ""),
            "source": row.get("source", ""),
            "sourceDate": source_date,
            "fresh": source_date == iso_date,
            "return1d": number(row.get("return_1d")) if row.get("return_1d") not in (None, "") else None,
            "returnUnit": "API原值",
            "rightSide": flag(row.get("is_trend_right_side")),
            "daysSinceEntry": number(row.get("days_since_trend_entry")) if row.get("days_since_trend_entry") not in (None, "") else None,
            "active": temperature in ACTIVE_TEMPERATURES,
        }
    return indexed


def quote_index(rows: list[dict[str, str]], report_date: str) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    iso_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    for row in rows:
        symbol = row.get("symbol", "").upper()
        if not symbol or row.get("status") != "OK":
            continue
        source_date = row.get("source_date", "")
        close = optional_number(row.get("close"))
        change_pct = optional_number(row.get("change_pct"))
        if close is None or change_pct is None:
            continue
        indexed[symbol] = {
            "close": close,
            "changePct": change_pct,
            "changeAmount": optional_number(row.get("change_amount")),
            "open": optional_number(row.get("open")),
            "high": optional_number(row.get("high")),
            "low": optional_number(row.get("low")),
            "contract": row.get("contract", ""),
            "source": row.get("source", "东方财富期货主力日线"),
            "sourceDate": source_date,
            "fresh": source_date == iso_date,
        }
    return indexed


def normalize_contract(value: str) -> str:
    contract = value.strip().lower()
    match = re.fullmatch(r"([a-z]+)(\d{3})", contract)
    return f"{match.group(1)}2{match.group(2)}" if match else contract


def ths_market_index(rows: list[dict[str, str]], report_date: str) -> dict[tuple[str, str], dict[str, object]]:
    indexed: dict[tuple[str, str], dict[str, object]] = {}
    iso_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    for row in rows:
        symbol = row.get("symbol", "").upper()
        contract = normalize_contract(row.get("contract", ""))
        if not symbol or not contract or row.get("status") != "OK" or row.get("source_date") != iso_date:
            continue
        source_date = row.get("source_date", "")
        indexed[(symbol, contract)] = {
            "quote": {
                "close": optional_number(row.get("close")),
                "changePct": optional_number(row.get("change_pct")),
                "contract": row.get("contract", ""),
                "source": row.get("source", "同花顺期货通桌面自选"),
                "sourceDate": source_date,
                "fresh": source_date == iso_date,
            },
            "marketFlow": {
                "capitalFlow": optional_number(row.get("capital_flow")),
                "openInterest": optional_number(row.get("open_interest")),
                "openInterestChange": optional_number(row.get("open_interest_change")),
                "openInterestChangePct": optional_number(row.get("open_interest_change_pct")),
                "return10d": optional_number(row.get("return_10d")),
                "return20d": optional_number(row.get("return_20d")),
                "return30d": optional_number(row.get("return_30d")),
                "monthlyReturn": optional_number(row.get("monthly_return")),
                "turnover": optional_number(row.get("turnover")),
                "volume": optional_number(row.get("volume")),
                "source": row.get("source", "同花顺期货通桌面自选"),
                "sourceDate": source_date,
                "fresh": source_date == iso_date,
            },
        }
    return indexed


def select_ths_market(
    markets: dict[tuple[str, str], dict[str, object]], symbol: str, contract: str
) -> dict[str, object] | None:
    exact = markets.get((symbol, normalize_contract(contract)))
    if exact:
        return exact
    candidates = [market for (market_symbol, _), market in markets.items() if market_symbol == symbol]
    if len(candidates) != 1:
        return None
    source = str(candidates[0].get("quote", {}).get("source", ""))
    return candidates[0] if re.fullmatch(r"[a-z]+m", contract.strip().lower()) or source == "同花顺期货通截图" else None


def technical_index(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).upper()
        if symbol:
            indexed[symbol] = item
    return indexed


def market_history(rows: list[dict[str, str]], report_date: str, value_fields: tuple[str, ...]) -> dict[str, list[dict[str, object]]]:
    indexed: dict[str, list[dict[str, object]]] = defaultdict(list)
    iso_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    for row in rows:
        symbol = row.get("symbol", "").upper()
        source_date = row.get("source_date", "")
        if not symbol or not source_date or source_date > iso_date or row.get("status") not in {"", "OK"}:
            continue
        item: dict[str, object] = {"sourceDate": source_date}
        for field in value_fields:
            item[field] = optional_number(row.get(field))
        indexed[symbol].append(item)
    for items in indexed.values():
        items.sort(key=lambda item: str(item["sourceDate"]))
    return indexed


def index_quote_history(rows: list[dict[str, str]], report_date: str) -> dict[str, dict[str, object]]:
    histories = market_history(rows, report_date, ("close", "change_pct"))
    result: dict[str, dict[str, object]] = {}
    iso_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    for symbol, items in histories.items():
        latest = items[-1]
        result[symbol] = {
            "close": latest.get("close"),
            "changePct": latest.get("change_pct"),
            "sourceDate": latest.get("sourceDate", ""),
            "fresh": latest.get("sourceDate") == iso_date,
            "source": "东方财富指数日线",
        }
    return result


def build_broker_rankings(
    rows: list[dict[str, str]], main_contracts: dict[str, str] | None = None
) -> dict[str, dict[str, list[dict[str, object]]]]:
    aggregated: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        symbol = row.get("symbol", "").upper()
        broker = row.get("broker", "")
        group = row.get("group", "")
        if not symbol or not broker:
            continue
        if main_contracts is not None and normalize_contract(row.get("contract", "")) != normalize_contract(main_contracts.get(symbol, "")):
            continue
        key = (symbol, group, broker)
        item = aggregated.setdefault(
            key,
            {"symbol": symbol, "group": group, "displayGroup": broker_display_group(broker, group), "broker": broker, "longPosition": 0.0, "shortPosition": 0.0, "netPosition": 0.0, "flowScore": 0.0, "longChange": 0.0, "shortChange": 0.0, "addLong": 0.0, "reduceLong": 0.0, "addShort": 0.0, "reduceShort": 0.0},
        )
        item["longPosition"] += number(row.get("long_pos"))
        item["shortPosition"] += number(row.get("short_pos"))
        item["netPosition"] += number(row.get("net_pos"))
        item["flowScore"] += number(row.get("flow_score"))
        item["longChange"] += number(row.get("long_chg"))
        item["shortChange"] += number(row.get("short_chg"))
        item["addLong"] += number(row.get("add_long"))
        item["reduceLong"] += number(row.get("reduce_long"))
        item["addShort"] += number(row.get("add_short"))
        item["reduceShort"] += number(row.get("reduce_short"))

    by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in aggregated.values():
        by_symbol[str(item["symbol"])].append(item)

    rankings: dict[str, dict[str, list[dict[str, object]]]] = {}
    for symbol, items in by_symbol.items():
        rankings[symbol] = {
            "netLong": sorted((item for item in items if item["netPosition"] > 0), key=lambda item: item["netPosition"], reverse=True)[:5],
            "netShort": sorted((item for item in items if item["netPosition"] < 0), key=lambda item: item["netPosition"])[:5],
        }
    return rankings


def build_broker_highlights(
    rows: list[dict[str, str]], margin_by_symbol: dict[str, float]
) -> dict[str, dict[str, list[dict[str, object]]]]:
    aggregated: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        symbol = row.get("symbol", "").upper()
        broker = row.get("broker", "")
        group = row.get("group", "")
        if not symbol or not broker or symbol in EXCLUDED_SYMBOLS:
            continue
        key = (group, broker, symbol)
        item = aggregated.setdefault(
            key,
            {
                "group": group,
                "displayGroup": broker_display_group(broker, group),
                "broker": broker,
                "symbol": symbol,
                "variety": row.get("variety", ""),
                "hands": 0.0,
                "amount": 0.0,
            },
        )
        hands = number(row.get("flow_score"))
        item["hands"] += hands
        item["amount"] += hands * margin_by_symbol.get(symbol, 0.0)

    result: dict[str, dict[str, list[dict[str, object]]]] = {}
    for group in ("内资", "外资", "家人"):
        items = [item for item in aggregated.values() if item["group"] == group]
        if group == "家人":
            for item in items:
                item["displayHands"] = -float(item["hands"])
                item["displayAmount"] = -float(item["amount"])
        else:
            for item in items:
                item["displayHands"] = float(item["hands"])
                item["displayAmount"] = float(item["amount"])
        result[group] = {
            "bullish": sorted(
                (item for item in items if float(item["displayAmount"]) > 0),
                key=lambda item: float(item["displayAmount"]),
                reverse=True,
            )[:5],
            "bearish": sorted(
                (item for item in items if float(item["displayAmount"]) < 0),
                key=lambda item: float(item["displayAmount"]),
            )[:5],
        }
    return result


def group_values(row: dict[str, str], prefix: str) -> dict[str, float]:
    return {
        "hands": number(row.get(f"{prefix}_flow_score")),
        "amount": number(row.get(f"{prefix}_amount_score")),
        "netPosition": number(row.get(f"{prefix}_net_pos")),
        "longChange": number(row.get(f"{prefix}_long_chg")),
        "shortChange": number(row.get(f"{prefix}_short_chg")),
    }


def build_instrument(
    amount_row: dict[str, str],
    hands_row: dict[str, str],
    trend: dict[str, object] | None,
    quote: dict[str, object] | None,
    market_flow: dict[str, object] | None,
    broker_ranking: dict[str, list[dict[str, object]]] | None,
    technical: dict[str, object] | None,
    basis_history: list[dict[str, object]] | None,
    warehouse_history: list[dict[str, object]] | None,
    source_plan: dict[str, object] | None,
    fundamental_facts: list[dict[str, object]] | None,
    wuxing_seasonality: dict[str, object] | None,
) -> dict[str, object]:
    domestic = group_values(amount_row, "domestic")
    foreign = group_values(amount_row, "foreign")
    family = group_values(amount_row, "family")
    family_reverse = {
        key: -value if key in {"hands", "amount", "netPosition", "longChange", "shortChange"} else value
        for key, value in family.items()
    }
    return {
        "variety": amount_row.get("variety", ""),
        "symbol": amount_row.get("symbol", "").upper(),
        "watchlist": amount_row.get("symbol", "").upper() in WATCHLIST_SYMBOLS,
        "sector": SECTOR_OVERRIDES.get(amount_row.get("symbol", "").upper(), amount_row.get("sector", "其他商品")),
        "direction": amount_row.get("signal_dir", "中性"),
        "handsSignal": number(hands_row.get("combined_signal")),
        "amountSignal": number(amount_row.get("combined_amount_signal")),
        "institutionHands": number(hands_row.get("institutional_score")),
        "institutionAmount": number(amount_row.get("institutional_amount_score")),
        "familyRawHands": number(hands_row.get("family_flow_score")),
        "familyRawAmount": number(amount_row.get("family_amount_score")),
        "totalPositionChange": number(hands_row.get("all_position_chg")),
        "totalActivity": number(hands_row.get("total_activity")),
        "totalActivityAmount": number(amount_row.get("total_activity_amount")),
        "marginalStructure": amount_row.get("institutional_marginal_structure", ""),
        "groups": {
            "domestic": domestic,
            "foreign": foreign,
            "family": family,
            "familyReverse": family_reverse,
        },
        "resonance": {
            "triple": flag(amount_row.get("triple_resonance")),
            "domesticForeign": flag(amount_row.get("domestic_foreign_same")),
            "familyReverse": flag(amount_row.get("family_reverse_resonance")),
            "label": amount_row.get("resonance_label", ""),
            "strength": number(amount_row.get("resonance_strength_amount")),
        },
        "margin": {
            "perLot": number(amount_row.get("domestic_margin_per_lot")),
            "rate": amount_row.get("domestic_margin_rate", ""),
            "contract": amount_row.get("domestic_margin_contract", ""),
            "exchange": amount_row.get("domestic_exchange", ""),
        },
        "trend": trend,
        "quote": quote,
        "marketFlow": market_flow,
        "brokerRanking": broker_ranking or {"netLong": [], "netShort": []},
        "technical": technical,
        "fundamentals": {
            "basis": basis_history or [],
            "warehouseReceipt": warehouse_history or [],
            "sourcePlan": source_plan or {},
            "facts": fundamental_facts or [],
        },
        "wuxingSeasonality": wuxing_seasonality,
    }


def build_stock_rows(
    rows: list[dict[str, str]],
    trends: dict[str, dict[str, object]],
    index_quotes: dict[str, dict[str, object]],
    ths_markets: dict[tuple[str, str], dict[str, object]],
) -> list[dict[str, object]]:
    result = []
    seen: set[str] = set()
    for row in rows:
        symbol = row.get("symbol", "").upper()
        if symbol not in {"IH", "IF", "IC", "IM"}:
            continue
        seen.add(symbol)
        ths_market = select_ths_market(ths_markets, symbol, row.get("domestic_margin_contract", ""))
        result.append(
            {
                "variety": row.get("variety", ""),
                "symbol": symbol,
                "direction": row.get("signal_dir", "中性"),
                "amountSignal": number(row.get("combined_amount_signal")),
                "domestic": number(row.get("domestic_amount_score")),
                "foreign": number(row.get("foreign_amount_score")),
                "familyReverse": -number(row.get("family_amount_score")),
                "trend": trends.get(symbol),
                "quote": ths_market["quote"] if ths_market else index_quotes.get(symbol),
                "marketFlow": ths_market["marketFlow"] if ths_market else None,
                "stockComponents": {
                    "机构": number(row.get("domestic_long_pos_amount")) - number(row.get("domestic_short_pos_amount")),
                    "外资": number(row.get("foreign_long_pos_amount")) - number(row.get("foreign_short_pos_amount")),
                    "家人反向": number(row.get("family_short_pos_amount")) - number(row.get("family_long_pos_amount")),
                },
                "flowComponents": {
                    "机构": number(row.get("domestic_amount_score")),
                    "外资": number(row.get("foreign_amount_score")),
                    "家人反向": -number(row.get("family_amount_score")),
                },
                "hasFuturesFlow": True,
            }
        )
    for symbol, variety in (("STAR50", "科创50"), ("GEM50", "创业板50")):
        if symbol not in seen:
            result.append(
                {
                    "variety": variety,
                    "symbol": symbol,
                    "direction": "观察",
                    "amountSignal": None,
                    "domestic": None,
                    "foreign": None,
                    "familyReverse": None,
                    "trend": trends.get(symbol),
                    "quote": index_quotes.get(symbol),
                    "hasFuturesFlow": False,
                }
            )
    return result


def build_sentiment(report_date: str) -> dict[str, object]:
    payload = read_json(ROOT / "data" / f"zsxq_equity_sentiment_summary_{report_date}.json")
    if not payload:
        return {"status": "unavailable", "dataDate": "", "fresh": False}
    iso_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    return {
        "status": payload.get("status", "unavailable"),
        "source": payload.get("source", "知识星球·趋势小程序"),
        "dataDate": payload.get("data_date", ""),
        "fresh": payload.get("data_date", "") == iso_date,
        "sampleCount": int(number(payload.get("sample_count"))),
        "topicCount": int(number(payload.get("topic_count"))),
        "commentCount": int(number(payload.get("comment_count"))),
        "nickCount": int(number(payload.get("nick_count"))),
        "score": number(payload.get("sentiment_score")),
        "label": payload.get("sentiment_label", ""),
        "confidence": payload.get("confidence", ""),
        "communitySummary": payload.get("community_summary", ""),
        "nickSummary": payload.get("nick_summary", ""),
        "methodology": payload.get("methodology", ""),
        "evidence": payload.get("evidence", [])[:4],
    }


def build_tide(instruments: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets = {
        "inflowUp": {"label": "资金流入 · 上涨", "items": []},
        "inflowDown": {"label": "资金流入 · 下跌", "items": []},
        "outflowUp": {"label": "资金流出 · 上涨", "items": []},
        "outflowDown": {"label": "资金流出 · 下跌", "items": []},
    }
    for item in instruments:
        quote = item.get("quote") or {}
        change_pct = quote.get("changePct")
        if change_pct is None or not quote:
            continue
        amount = float(item["amountSignal"])
        key = ("inflow" if amount >= 0 else "outflow") + ("Up" if float(change_pct) >= 0 else "Down")
        buckets[key]["items"].append(
            {
                "symbol": item["symbol"],
                "variety": item["variety"],
                "amount": amount,
                "changePct": change_pct,
                "structure": item["marginalStructure"],
            }
        )
    for bucket in buckets.values():
        bucket["items"].sort(key=lambda item: abs(float(item["amount"])), reverse=True)
        bucket["count"] = len(bucket["items"])
        bucket["items"] = bucket["items"][:5]
    return [buckets[key] for key in ("inflowUp", "inflowDown", "outflowUp", "outflowDown")]


def build_trend_resonance(instruments: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for item in instruments:
        trend = item.get("trend") or {}
        temperature = trend.get("temperature", "")
        if temperature not in ACTIVE_TEMPERATURES:
            continue
        trend_sign = 1 if temperature in {"温", "热", "沸"} else -1
        money_sign = 1 if float(item["amountSignal"]) > 0 else -1 if float(item["amountSignal"]) < 0 else 0
        result.append(
            {
                "symbol": item["symbol"],
                "variety": item["variety"],
                "sector": item["sector"],
                "temperature": temperature,
                "strength": trend.get("strength", 0),
                "stage": trend.get("stage", ""),
                "rightSide": trend.get("rightSide", False),
                "sourceDate": trend.get("sourceDate", ""),
                "fresh": trend.get("fresh", False),
                "amount": item["amountSignal"],
                "hands": item["handsSignal"],
                "relation": "资金顺势" if money_sign == trend_sign else "资金逆势" if money_sign else "资金未验证",
                "watchlist": item.get("watchlist", False),
            }
        )
    result.sort(key=lambda item: (not bool(item["watchlist"]), item["relation"] != "资金顺势", -abs(float(item["amount"]))))
    return result


def build_weather(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    severity = {"high": 3, "medium": 2, "low": 1}
    ordered = sorted(
        rows,
        key=lambda row: (severity.get(row.get("risk_level", ""), 0), number(row.get("risk_score"))),
        reverse=True,
    )
    return [
        {
            "window": row.get("alert_window", ""),
            "date": row.get("alert_date", ""),
            "sector": row.get("sector", ""),
            "symbol": row.get("symbol", ""),
            "variety": row.get("variety", ""),
            "level": row.get("risk_level", ""),
            "score": number(row.get("risk_score")),
            "types": row.get("risk_types", ""),
            "origins": row.get("origins", ""),
            "reason": row.get("trigger_reason", ""),
            "reflection": row.get("market_reflection", ""),
        }
        for row in ordered
    ]


def validate_seat_evidence(
    snapshot: dict[str, object], position_rows: list[dict[str, str]], report_date: str
) -> None:
    instruments = snapshot.get("instruments", [])
    source_symbols = {
        row.get("symbol", "").upper()
        for row in position_rows
        if row.get("symbol") and row.get("contract") and row.get("broker")
    }
    missing_source = []
    missing_long = []
    missing_short = []
    for item in instruments if isinstance(instruments, list) else []:
        symbol = str(item.get("symbol", "")).upper()
        ranking = item.get("brokerRanking") or {}
        if symbol not in source_symbols:
            missing_source.append(symbol)
        if not ranking.get("netLong"):
            missing_long.append(symbol)
        if not ranking.get("netShort"):
            missing_short.append(symbol)
    if missing_source or missing_long or missing_short:
        details = []
        if missing_source:
            details.append(f"source rows missing: {','.join(missing_source)}")
        if missing_long:
            details.append(f"net-long seats missing: {','.join(missing_long)}")
        if missing_short:
            details.append(f"net-short seats missing: {','.join(missing_short)}")
        raise RuntimeError(f"Incomplete seat evidence for {report_date}: {'; '.join(details)}")


SEAT_FLOW_FOREIGN = ["高盛期货", "瑞银期货", "摩根大通"]
SEAT_FLOW_DOMESTIC = ["国泰君安", "东证期货", "永安期货", "中财期货", "东吴期货"]
SEAT_FLOW_EXCLUDED_SYMBOLS = {"IH", "IF", "IC", "IM", "T", "TF", "TS", "TL"}
SEAT_FLOW_TOP_N = 5


def build_seat_flow(report_date: str) -> dict[str, object] | None:
    """席位大资金动向：外资/内资两组，各自汇总成员席位当日净持仓变化的前五流多与前五流空。

    口径（2026-09-11 与用户确认）：
    - 每席位每品种净变化 = Σ(long_chg) - Σ(short_chg)（多合约合计），剔除股指与国债。
    - 每席位取净变化前五流多与前五流空；组内对席位入选品种取并集（可超过五个），
      品种净变化为组内合计，并记录入选席位。
    - 数据来自 scripts/fetch_seat_flow.py 产出的 data/seat_flow_rows_YYYYMMDD.json；
      文件或席位缺失时返回 None / 空组，不伪造。
    """
    rows_path = ROOT / "data" / f"seat_flow_rows_{report_date}.json"
    payload = read_json(rows_path)
    if not isinstance(payload, dict) or not payload.get("brokers"):
        return None

    def group_flow(broker_names: list[str]) -> dict[str, object] | None:
        per_broker_top: dict[str, dict[str, set[str]]] = {}
        variety_change: dict[str, float] = {}
        variety_symbol: dict[str, str] = {}
        variety_brokers: dict[str, set[str]] = defaultdict(set)
        for broker in broker_names:
            rows = payload["brokers"].get(broker) or []
            variety_net: dict[str, float] = {}
            for row in rows:
                symbol = str(row.get("symbol") or "").upper()
                if symbol in SEAT_FLOW_EXCLUDED_SYMBOLS:
                    continue
                variety = str(row.get("variety") or "")
                if not variety or "股指" in variety or "国债" in variety:
                    continue
                try:
                    change = float(row.get("long_chg") or 0) - float(row.get("short_chg") or 0)
                except (TypeError, ValueError):
                    continue
                variety_net[variety] = variety_net.get(variety, 0.0) + change
                variety_symbol[variety] = symbol
            if not variety_net:
                continue
            ranked = sorted(variety_net.items(), key=lambda kv: kv[1])
            top_short = [variety for variety, change in ranked[:SEAT_FLOW_TOP_N] if change < 0]
            top_long = [variety for variety, change in sorted(ranked, key=lambda kv: kv[1], reverse=True)[:SEAT_FLOW_TOP_N] if change > 0]
            per_broker_top[broker] = {"long": set(top_long), "short": set(top_short)}
            for variety, change in variety_net.items():
                variety_change[variety] = variety_change.get(variety, 0.0) + change
            for variety in set(top_long) | set(top_short):
                variety_brokers[variety].add(broker)
        if not per_broker_top:
            return None
        long_union: set[str] = set()
        short_union: set[str] = set()
        for tops in per_broker_top.values():
            long_union |= tops["long"]
            short_union |= tops["short"]

        def entry(variety: str) -> dict[str, object]:
            return {
                "variety": variety,
                "symbol": variety_symbol.get(variety, ""),
                "netChange": int(round(variety_change.get(variety, 0.0))),
                "brokers": sorted(variety_brokers.get(variety, set())),
            }

        top_long = sorted((entry(variety) for variety in long_union), key=lambda e: e["netChange"], reverse=True)
        top_short = sorted((entry(variety) for variety in short_union), key=lambda e: e["netChange"])
        return {"topLong": top_long, "topShort": top_short, "brokers": sorted(per_broker_top)}

    return {
        "date": payload.get("date", report_date),
        "fetchedAt": payload.get("fetchedAt", ""),
        "foreign": group_flow(SEAT_FLOW_FOREIGN),
        "domestic": group_flow(SEAT_FLOW_DOMESTIC),
    }


def build_snapshot(report_date: str) -> dict[str, object]:
    institutional_dir = OUTPUT_ROOT / f"institutional_seat_report_{report_date}" / "data"
    amount_dir = OUTPUT_ROOT / f"margin_weighted_seat_report_{report_date}" / "data"
    hands_rows = read_csv(institutional_dir / "institutional_resonance.csv")
    amount_rows = read_csv(amount_dir / "institutional_amount_resonance.csv")
    hands_by_symbol = row_index(hands_rows)
    fetch_rows = read_csv(institutional_dir / "fetch_status.csv")
    disclosure_dates = sorted({row.get("date", "") for row in fetch_rows if row.get("date")})
    current_trend_file = ROOT / "data" / f"trend_temperature_{report_date}.csv"
    fallback_trend_file = latest_dated_file("trend_temperature_*.csv", report_date)
    trend_file = current_trend_file if current_trend_file.exists() else fallback_trend_file
    trend_rows = read_csv(trend_file) if trend_file else read_csv(amount_dir / "trend_temperature_used.csv")
    trends = trend_index(trend_rows, report_date)
    current_quote_file = ROOT / "data" / f"sina_quhe_main_quotes_{report_date}.csv"
    legacy_quote_file = ROOT / "data" / f"eastmoney_main_quotes_{report_date}.csv"
    quote_file = current_quote_file if current_quote_file.exists() else legacy_quote_file if legacy_quote_file.exists() else None
    quotes = quote_index(read_csv(quote_file) if quote_file else [], report_date)
    ths_file = ROOT / "data" / f"ths_main_quotes_{report_date}.csv"
    ths_markets = ths_market_index(read_csv(ths_file), report_date)
    technicals = technical_index(read_json(ROOT / "data" / f"eastmoney_technical_snapshot_{report_date}.json"))
    wuxing_file = latest_dated_file("wuxing_month_seasonality_*.json", report_date)
    wuxing_payload = read_json(wuxing_file) if wuxing_file else {}
    wuxing_methodology = wuxing_payload.get("methodology", {}) if isinstance(wuxing_payload, dict) else {}
    wuxing_calendar = wuxing_payload.get("monthCalendar", []) if isinstance(wuxing_payload, dict) else []
    wuxing_results = wuxing_payload.get("instruments", {}) if isinstance(wuxing_payload, dict) else {}
    basis_file = latest_dated_file("futures_basis_history_*.csv", report_date)
    warehouse_file = latest_dated_file("eastmoney_warehouse_receipts_*.csv", report_date)
    index_quote_file = latest_dated_file("eastmoney_index_quotes_*.csv", report_date)
    mysteel_fact_file = latest_dated_file("mysteel_fundamental_facts_*.csv", report_date)
    basis_by_symbol = market_history(read_csv(basis_file) if basis_file else [], report_date, ("spot_price", "main_price", "basis", "basis_pct"))
    warehouse_by_symbol = market_history(read_csv(warehouse_file) if warehouse_file else [], report_date, ("warehouse_receipt", "change"))
    index_quotes = index_quote_history(read_csv(index_quote_file) if index_quote_file else [], report_date)
    contract_rows = read_csv(institutional_dir / "contract_rows.csv")
    broker_groups = {row.get("broker", ""): row.get("group", "") for row in contract_rows if row.get("broker")}
    full_position_rows = read_csv(ROOT / "data" / f"qhkch_main_position_rows_{report_date}.csv")
    for row in full_position_rows:
        row["group"] = broker_groups.get(row.get("broker", ""), "内资")
    contracts_by_symbol: dict[str, set[str]] = defaultdict(set)
    for row in full_position_rows:
        if row.get("symbol") and row.get("contract"):
            contracts_by_symbol[row["symbol"].upper()].add(row["contract"])
    position_contracts = {
        symbol: next(iter(contracts))
        for symbol, contracts in contracts_by_symbol.items()
        if len(contracts) == 1
    }
    broker_rankings = build_broker_rankings(
        full_position_rows or contract_rows,
        {
            row.get("symbol", "").upper(): position_contracts.get(row.get("symbol", "").upper())
            or quotes.get(row.get("symbol", "").upper(), {}).get("contract")
            or row.get("domestic_margin_contract", "")
            for row in amount_rows
            if row.get("symbol")
        },
    )
    source_plans = fundamental_source_plans()
    mysteel_facts = fundamental_fact_index(read_csv(mysteel_fact_file) if mysteel_fact_file else [], report_date)
    qhkch_overview = read_json(ROOT / "data" / f"qhkch_variety_overview_{report_date}.json")

    instruments = []
    for amount_row in amount_rows:
        symbol = amount_row.get("symbol", "").upper()
        sector = SECTOR_OVERRIDES.get(symbol, amount_row.get("sector", ""))
        if not symbol or symbol in EXCLUDED_SYMBOLS or sector not in ANALYSIS_SECTORS:
            continue
        ths_contract = quotes.get(symbol, {}).get("contract") or amount_row.get("domestic_margin_contract", "")
        ths_market = select_ths_market(ths_markets, symbol, str(ths_contract))
        instruments.append(
            build_instrument(
                amount_row,
                hands_by_symbol.get(symbol, {}),
                trends.get(symbol),
                ths_market["quote"] if ths_market else quotes.get(symbol),
                ths_market["marketFlow"] if ths_market else None,
                broker_rankings.get(symbol),
                technicals.get(symbol),
                basis_by_symbol.get(symbol),
                warehouse_by_symbol.get(symbol),
                source_plans.get(symbol),
                mysteel_facts.get(symbol),
                (
                    {
                        **wuxing_results[symbol],
                        "reportDate": wuxing_payload.get("reportDate", ""),
                        "source": wuxing_payload.get("source", ""),
                        "methodology": wuxing_methodology,
                        "monthCalendar": wuxing_calendar,
                    }
                    if symbol in wuxing_results
                    else None
                ),
            )
        )

    instruments.sort(key=lambda item: abs(float(item["amountSignal"])), reverse=True)
    triples = [item for item in instruments if item["resonance"]["triple"]]
    bullish = [item for item in instruments if item["amountSignal"] > 0]
    bearish = [item for item in instruments if item["amountSignal"] < 0]
    sectors: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(lambda: {"bullish": [], "bearish": []})
    for item in instruments:
        target = "bullish" if item["amountSignal"] > 0 else "bearish"
        sectors[str(item["sector"])][target].append(item)
    sector_summary = []
    for sector, sides in sectors.items():
        for side in sides.values():
            side.sort(key=lambda item: abs(float(item["amountSignal"])), reverse=True)
        sector_summary.append(
            {
                "sector": sector,
                "bullishCount": len(sides["bullish"]),
                "bearishCount": len(sides["bearish"]),
                "bullish": [{"symbol": item["symbol"], "variety": item["variety"], "value": item["amountSignal"]} for item in sides["bullish"][:3]],
                "bearish": [{"symbol": item["symbol"], "variety": item["variety"], "value": item["amountSignal"]} for item in sides["bearish"][:3]],
            }
        )
    sector_summary.sort(key=lambda item: item["sector"])

    margin_status = read_csv(amount_dir / "margin_fetch_status.csv")
    margin_source = margin_status[0] if margin_status else {}
    margin_by_symbol = {str(item["symbol"]): float(item["margin"]["perLot"]) for item in instruments}
    covered = sum(1 for item in instruments if item["margin"]["perLot"] > 0)
    trend_fresh = sum(1 for item in instruments if item.get("trend") and item["trend"].get("fresh"))
    quote_fresh = sum(1 for item in instruments if item.get("quote") and item["quote"].get("fresh"))
    status_counts = defaultdict(int)
    for row in fetch_rows:
        status_counts[row.get("note", "UNKNOWN")] += 1
    instrument_by_symbol = {str(item["symbol"]): item for item in instruments}
    key_events = []
    for event in qhkch_overview.get("events", []) if isinstance(qhkch_overview, dict) else []:
        instrument = instrument_by_symbol.get(str(event.get("symbol", "")).upper(), {})
        market_flow = instrument.get("marketFlow") or {}
        quote = instrument.get("quote") or {}
        key_events.append({
            **event,
            "priceChangePct": quote.get("changePct", event.get("priceChangePct")),
            "openInterestChangePct": market_flow.get("openInterestChangePct", event.get("openInterestChangePct")),
            "turnover": market_flow.get("turnover", event.get("turnover")),
        })

    return {
        "date": report_date,
        "disclosureDates": disclosure_dates,
        "summary": {
            "instrumentCount": len(instruments),
            "bullishCount": len(bullish),
            "bearishCount": len(bearish),
            "tripleCount": len(triples),
            "strongestBullish": bullish[0] if bullish else None,
            "strongestBearish": bearish[0] if bearish else None,
            "marginCoverage": covered / len(instruments) if instruments else 0,
            "trendFreshCount": trend_fresh,
            "quoteFreshCount": quote_fresh,
            "domesticForeignSameCount": sum(1 for item in instruments if item["resonance"]["domesticForeign"]),
            "familyReverseCount": sum(1 for item in instruments if item["resonance"]["familyReverse"]),
            "watchlistCovered": sum(1 for item in instruments if item.get("watchlist")),
            "fetchStatus": dict(status_counts),
            "marginSourceUpdate": margin_source.get("source_update", ""),
            "marginCacheNote": margin_source.get("note", ""),
            "trendSourceFile": trend_file.name if trend_file else "",
            "quoteSourceFile": quote_file.name if quote_file else "",
            "thsSourceFile": ths_file.name if ths_file.exists() else "",
            "thsMarketCoveredCount": sum(1 for item in instruments if item.get("marketFlow")),
            "quoteSource": "曲合期货主力行情；新浪财经主力合约日线与实时收盘校验",
            "basisSourceFile": basis_file.name if basis_file else "",
            "warehouseSourceFile": warehouse_file.name if warehouse_file else "",
            "mysteelFundamentalSourceFile": mysteel_fact_file.name if mysteel_fact_file else "",
            "wuxingSourceFile": wuxing_file.name if wuxing_file else "",
            "basisCoveredCount": sum(1 for item in instruments if item["fundamentals"]["basis"]),
            "warehouseCoveredCount": sum(1 for item in instruments if item["fundamentals"]["warehouseReceipt"]),
            "fundamentalSourcePlanCount": sum(1 for item in instruments if item["fundamentals"]["sourcePlan"]),
            "mysteelFundamentalCoveredCount": sum(1 for item in instruments if item["fundamentals"]["facts"]),
        },
        "sectorSummary": sector_summary,
        "tripleResonance": triples,
        "tide": build_tide(instruments),
        "keyEvents": key_events,
        "trendResonance": build_trend_resonance(instruments),
        "brokerHighlights": build_broker_highlights(contract_rows, margin_by_symbol),
        "seatFlow": build_seat_flow(report_date),
        "instruments": instruments,
        "weather": build_weather(read_csv(institutional_dir / "agri_weather_risk.csv")),
        "stockIndices": build_stock_rows(read_csv(amount_dir / "stock_index_amount_resonance.csv"), trends, index_quotes, ths_markets),
        "equitySentiment": build_sentiment(report_date),
    }


def main() -> None:
    common_dates = sorted(
        discover_dates("institutional_seat_report") & discover_dates("margin_weighted_seat_report"),
        reverse=True,
    )
    if not common_dates:
        raise SystemExit("No common institutional and margin-weighted snapshots were found.")

    requested_date = os.environ.get("REPORT_DATE", "").strip()
    target_date = requested_date or common_dates[0]
    if target_date not in common_dates[:30]:
        raise SystemExit(f"No build inputs were found for REPORT_DATE={target_date}.")
    generated_snapshots = {date: build_snapshot(date) for date in common_dates[:30]}
    validate_seat_evidence(
        generated_snapshots[target_date],
        read_csv(ROOT / "data" / f"qhkch_main_position_rows_{target_date}.csv"),
        target_date,
    )
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for date, snapshot in generated_snapshots.items():
        with (SNAPSHOT_DIR / f"{date}.json").open("w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"))

    persisted_snapshots: dict[str, dict[str, object]] = {}
    for path in SNAPSHOT_DIR.glob("*.json"):
        if re.fullmatch(r"\d{8}", path.stem):
            payload = read_json(path)
            if payload:
                persisted_snapshots[path.stem] = payload
    snapshots = {
        date: persisted_snapshots[date]
        for date in sorted(persisted_snapshots, reverse=True)[:30]
    }
    history: list[dict] = []
    for date in sorted(snapshots):
        history.append(snapshots[date])
        snapshots[date]["cta"] = build_cta_rows(history, load_loss_rows(date), load_option_rows(date))
        with (SNAPSHOT_DIR / f"{date}.json").open("w", encoding="utf-8") as handle:
            json.dump(snapshots[date], handle, ensure_ascii=False, separators=(",", ":"))
    generated_at = datetime.now(BEIJING)
    payload = {
        "generatedAt": generated_at.isoformat(timespec="seconds"),
        "dates": list(snapshots),
        "latestDate": next(iter(snapshots)),
        "snapshots": snapshots,
    }

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for asset in ("index.html", "styles.css", "app.js", "history-store.js"):
        shutil.copy2(SOURCE_DIR / asset, TARGET_DIR / asset)
    imported_source = SOURCE_DIR / "data" / "imported"
    if imported_source.is_dir():
        imported_target = TARGET_DIR / "data" / "imported"
        imported_target.mkdir(parents=True, exist_ok=True)
        for item in imported_source.glob("*.json"):
            shutil.copy2(item, imported_target / item.name)
    build_version = datetime.now().strftime("%Y%m%d%H%M%S")
    index_path = TARGET_DIR / "index.html"
    index_html = index_path.read_text(encoding="utf-8")
    # 版本戳：正则容忍 ./ 前缀与既有 ?v=（旧写法精确匹配 'src="app.js"'，
    # 对实际引用 './app.js?v=...' 全部静默失效，戳永远停在首次手写值）
    index_html = re.sub(r'(href="(?:\./)?styles(?:-v2)?\.css)(?:\?v=[^"]*)?"', rf'\1?v={build_version}"', index_html)
    index_html = re.sub(r'(src="(?:\./)?(?:app|history-store|journal-sync)\.js)(?:\?v=[^"]*)?"', rf'\1?v={build_version}"', index_html)
    index_path.write_text(index_html, encoding="utf-8")
    data_dir = TARGET_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    with (data_dir / "dashboard.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    # 首屏加速：页面先拉这份几 KB 的 meta + 最新日快照，其余历史快照由 app.js 按需补载
    meta_payload = {
        "generatedAt": payload["generatedAt"],
        "dates": payload["dates"],
        "latestDate": payload["latestDate"],
    }
    with (data_dir / "dashboard-meta.json").open("w", encoding="utf-8") as handle:
        json.dump(meta_payload, handle, ensure_ascii=False, separators=(",", ":"))
    latest_summary = snapshots[payload["latestDate"]]["summary"]
    manifest = {
        "schemaVersion": 1,
        "runId": f"{payload['latestDate']}-{generated_at.strftime('%Y%m%dT%H%M%S%z')}",
        "generatedAt": payload["generatedAt"],
        "latestDate": payload["latestDate"],
        "snapshotCount": len(snapshots),
        "snapshotDates": list(snapshots),
        "sourceFiles": {
            key: latest_summary.get(key, "")
            for key in (
                "trendSourceFile",
                "quoteSourceFile",
                "thsSourceFile",
                "basisSourceFile",
                "warehouseSourceFile",
                "mysteelFundamentalSourceFile",
            )
        },
        "outputs": ["index.html", "styles.css", "app.js", "data/dashboard.json"],
    }
    with (TARGET_DIR / "run-manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    print(f"Built {TARGET_DIR / 'index.html'} with {len(snapshots)} snapshots.")


if __name__ == "__main__":
    main()
