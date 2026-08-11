"""Fetch a bounded Trend Animal snapshot for the focus commodities.

The API key is read only from TREND_ANIMAL_API_KEY.  Neither this script nor
its generated files persist the key or a request URL containing it.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


ROOT = Path.cwd()
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
API_BASE = "https://www.trendtrader.cn/apiData/data/"
API_KEY = os.environ.get("TREND_ANIMAL_API_KEY", "").strip()
DAILY_COST_ALERT_YUAN = float(os.environ.get("TREND_ANIMAL_DAILY_COST_ALERT", "1.00"))

FOCUS_ITEMS = [
    ("FU", "燃油", "燃油"),
    ("EB", "苯乙烯", "苯乙烯"),
    ("LC", "碳酸锂", "碳酸锂"),
    ("M", "豆粕", "豆粕"),
    ("JM", "焦煤", "焦煤"),
    ("I", "铁矿石", "铁矿石"),
    ("JD", "鸡蛋", "鸡蛋"),
    ("AU", "黄金", "沪金"),
    ("AG", "白银", "沪银"),
    ("EC", "集运欧线", "集运欧线"),
    ("LH", "生猪", "生猪"),
    ("P", "棕榈油", "棕榈油"),
    ("RU", "天然橡胶", "天然橡胶"),
]

INDEX_ITEMS = [
    ("IH", "上证50", "上证50"),
    ("IF", "沪深300", "沪深300"),
    ("IC", "中证500", "中证500"),
    ("IM", "中证1000", "中证1000"),
    ("STAR50", "科创50", "科创50"),
    ("GEM50", "创业板50", "创业板50"),
]

# These are the smallest fields needed for the report's trend-temperature and
# right-side interpretation.  Their current cost is read from the API at run
# time rather than embedded in the script.
SNAPSHOT_FIELDS = [
    "trendTemperatureCurr",
    "trendTemperaturePrev",
    "isTrendRightSide",
    "daysSinceTrendEntry",
    "trendPhaseCurr",
    "trendStrengthLocalCurr",
    "trendStrengthLocalChange",
    "return1d",
]


def api_get(endpoint: str, **params: object) -> dict:
    query = urlencode({"apiKey": API_KEY, **params})
    with urlopen(f"{API_BASE}{endpoint}?{query}", timeout=30) as response:
        payload = json.load(response)
    if payload.get("code") != "00000" or not payload.get("success", False):
        raise RuntimeError(f"{endpoint} failed: {payload.get('msg', 'unknown error')}")
    return payload


def pause() -> None:
    # searchTicker and the free metadata endpoints are limited to 1 request/s.
    time.sleep(1.05)


def select_commodity_future(candidates: list[dict], symbol: str, display_name: str) -> dict | None:
    eligible = [item for item in candidates if item.get("asset") == "商品期货"]
    if not eligible:
        return None

    expected = symbol.upper()

    def score(item: dict) -> tuple[int, str]:
        item_symbol = str(item.get("tickerSymbol", "")).upper()
        name = str(item.get("tickerName", ""))
        return (
            int(item_symbol == expected) * 4
            + int(item_symbol.startswith(expected)) * 2
            + int(name == display_name) * 3
            + int(display_name in name),
            item_symbol,
        )

    return sorted(eligible, key=score, reverse=True)[0]


def select_index(candidates: list[dict], display_name: str) -> dict | None:
    eligible = [
        item
        for item in candidates
        if "指数" in str(item.get("asset", "")) or "指数" in str(item.get("tickerName", ""))
    ]
    if not eligible:
        return None

    def score(item: dict) -> tuple[int, str]:
        name = str(item.get("tickerName", ""))
        asset = str(item.get("asset", ""))
        return (
            int(name == display_name) * 8
            + int(display_name in name) * 4
            + int("指数" in asset) * 2
            - int("ETF" in name) * 5
            - int("期货" in name) * 2,
            name,
        )

    return sorted(eligible, key=score, reverse=True)[0]


def safe_number(value: object) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def daily_cost_alert_triggered(target_date: str) -> bool:
    """Check today's actual API ledger without persisting billing details."""
    ledger = api_get("getAccountBalance", viewLevel="ledger")
    daily_cost = 0.0
    for item in ledger.get("data", []):
        if str(item.get("txnType", "")) != "C":
            continue
        if not str(item.get("insDt", "")).startswith(target_date):
            continue
        daily_cost += float(item.get("apiCost") or 0)
    return daily_cost > DAILY_COST_ALERT_YUAN


def main() -> None:
    if not API_KEY:
        raise SystemExit("TREND_ANIMAL_API_KEY is required; no API call was made.")

    docs = api_get("getApiDocIntro")
    pause()
    change_log = api_get("getChangeLog")
    pause()
    update_status = api_get("getUpdateStatus")
    pause()
    billing = api_get("getSnapshotColumnBilling")

    commodity_status = next(
        (item for item in update_status.get("data", []) if item.get("asset") == "商品期货"),
        None,
    )
    if commodity_status is None:
        raise RuntimeError("getUpdateStatus did not return a 商品期货 update status.")

    target_date = f"{RUN_DATE[:4]}-{RUN_DATE[4:6]}-{RUN_DATE[6:]}"
    if str(commodity_status.get("asOfDate", "")) != target_date:
        raise RuntimeError(
            f"Commodity futures data is stale: {commodity_status.get('asOfDate', '-')}; "
            f"expected {target_date}. Snapshot request was skipped."
        )

    billing_by_column = {item.get("columnName"): item for item in billing.get("data", [])}
    missing_fields = [field for field in SNAPSHOT_FIELDS if field not in billing_by_column]
    if missing_fields:
        raise RuntimeError(f"getSnapshotColumnBilling did not list: {', '.join(missing_fields)}")
    per_row_cost = sum(float(billing_by_column[field].get("priceCost") or 0) for field in SNAPSHOT_FIELDS)

    selected: list[dict] = []
    unresolved: list[str] = []
    for symbol, display_name, keyword in FOCUS_ITEMS:
        pause()
        found = api_get("searchTicker", keyword=keyword).get("data", [])
        match = select_commodity_future(found, symbol, display_name)
        if match is None:
            unresolved.append(f"{symbol}:{keyword}")
            continue
        selected.append({"symbol": symbol, "display_name": display_name, "report_scope": "commodity", **match})

    status_by_asset = {str(item.get("asset", "")): item for item in update_status.get("data", [])}
    for symbol, display_name, keyword in INDEX_ITEMS:
        pause()
        found = api_get("searchTicker", keyword=keyword).get("data", [])
        match = select_index(found, display_name)
        if match is None:
            unresolved.append(f"{symbol}:{keyword}")
            continue
        asset_status = status_by_asset.get(str(match.get("asset", "")))
        if asset_status is None or str(asset_status.get("asOfDate", "")) != target_date:
            unresolved.append(f"{symbol}:asset data stale or status missing")
            continue
        selected.append({"symbol": symbol, "display_name": display_name, "report_scope": "stock_index", **match})

    estimated_cost = len(selected) * per_row_cost + (len(FOCUS_ITEMS) + len(INDEX_ITEMS)) * 0.01
    if not selected:
        raise RuntimeError("No focus commodity futures could be resolved by searchTicker.")

    snapshot = api_get(
        "getTickerSnapshot",
        tmIds=",".join(str(item["tmId"]) for item in selected),
        fields=",".join(SNAPSHOT_FIELDS),
    )
    snapshot_by_id = {str(item.get("tmId")): item for item in snapshot.get("data", [])}
    cost_alert = daily_cost_alert_triggered(target_date)

    rows = []
    for item in selected:
        fact = snapshot_by_id.get(str(item["tmId"]), {})
        if not fact:
            unresolved.append(f"{item['symbol']}:snapshot missing")
            continue
        rows.append(
            {
                "snapshot_date": fact.get("asOfDate", commodity_status.get("asOfDate", "")),
                "symbol": item["symbol"],
                "variety": item["display_name"],
                "report_scope": item.get("report_scope", "commodity"),
                "asset": item.get("asset", ""),
                "temperature": fact.get("trendTemperatureCurr", ""),
                "strength": safe_number(fact.get("trendStrengthLocalCurr")),
                "trend_rank": "",
                "source": "trend_animal_api",
                "note": "API direct fact",
                "tm_id": item["tmId"],
                "ticker_symbol": fact.get("tickerSymbol", item.get("tickerSymbol", "")),
                "is_trend_right_side": fact.get("isTrendRightSide", ""),
                "days_since_trend_entry": safe_number(fact.get("daysSinceTrendEntry")),
                "trend_phase_curr": fact.get("trendPhaseCurr", ""),
                "trend_temperature_prev": fact.get("trendTemperaturePrev", ""),
                "trend_strength_local_change": safe_number(fact.get("trendStrengthLocalChange")),
                "return_1d": safe_number(fact.get("return1d")),
                "api_update_dt": commodity_status.get("updateDt", ""),
            }
        )

    output = ROOT / "data" / f"trend_temperature_{RUN_DATE}.csv"
    status_output = ROOT / "data" / f"trend_animal_fetch_status_{RUN_DATE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8-sig")
    status_output.write_text(
        json.dumps(
            {
                "source": "Trend Animal API",
                "run_date": RUN_DATE,
                "commodity_update": {
                    "asOfDate": commodity_status.get("asOfDate", ""),
                    "updateDt": commodity_status.get("updateDt", ""),
                },
                "asset_updates": {
                    asset: {"asOfDate": value.get("asOfDate", ""), "updateDt": value.get("updateDt", "")}
                    for asset, value in status_by_asset.items()
                    if asset in {str(item.get("asset", "")) for item in selected}
                },
                "requested_fields": SNAPSHOT_FIELDS,
                "per_row_cost_yuan": per_row_cost,
                "estimated_cost_yuan": estimated_cost,
                "daily_cost_alert_triggered": cost_alert,
                "daily_cost_alert_threshold_yuan": DAILY_COST_ALERT_YUAN,
                "resolved_count": len(rows),
                "commodity_count": sum(row.get("report_scope") == "commodity" for row in rows),
                "stock_index_count": sum(row.get("report_scope") == "stock_index" for row in rows),
                "unresolved": unresolved,
                "doc_version_entries": len(docs.get("data", [])),
                "change_log_latest": (change_log.get("data") or [])[:3],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"trend snapshot: {output}")
    print(f"status: {status_output}")
    print(f"resolved: {len(rows)}/{len(FOCUS_ITEMS) + len(INDEX_ITEMS)}")
    print(f"estimated cost: {estimated_cost:.3f} yuan")
    if cost_alert:
        print("TREND_API_DAILY_COST_ALERT: today's API spend exceeded the configured threshold.")


if __name__ == "__main__":
    main()
