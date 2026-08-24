"""Fetch report-date closing quotes for Eastmoney domestic main futures contracts."""

from __future__ import annotations

import csv
import html as html_lib
import http.client
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote_plus, urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PAGE = "https://qhweb.eastmoney.com/quote/zhuli"
QHKCH_OVERVIEW_URL = "https://x.qhkch.com/variety"
MAIN_LIST_URL = "https://futsseapi.eastmoney.com/list/trans/block/risk/mk0830"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
USER_AGENT = "Mozilla/5.0"
LIST_FIELDS = "name,p,zdf,dm,sc,uid,zsjd"
KLINE_FIELDS_1 = "f1,f2,f3,f4,f5,f6,f7,f8"
KLINE_FIELDS_2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
MAX_WORKERS = 2
MAX_ATTEMPTS = 4


def valid_quote_value(value: object) -> bool:
    if value in (None, "", "-", "--"):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def valid_quote_row(row: dict[str, object]) -> bool:
    return (
        row.get("status") == "OK"
        and bool(row.get("source_date"))
        and valid_quote_value(row.get("close"))
        and valid_quote_value(row.get("change_pct"))
    )


def get_json(url: str, params: dict[str, object]) -> dict:
    request_url = f"{url}?{urlencode(params)}"
    for attempt in range(MAX_ATTEMPTS):
        request = Request(request_url, headers={"User-Agent": USER_AGENT, "Referer": SOURCE_PAGE})
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, http.client.RemoteDisconnected):
            if attempt + 1 == MAX_ATTEMPTS:
                raise
            time.sleep((0.6 * (2 ** attempt)) + random.uniform(0.0, 0.25))
    raise RuntimeError("Eastmoney request retry loop ended unexpectedly.")


def get_text(url: str) -> str:
    for attempt in range(MAX_ATTEMPTS):
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, http.client.RemoteDisconnected):
            if attempt + 1 == MAX_ATTEMPTS:
                raise
            time.sleep((0.6 * (2 ** attempt)) + random.uniform(0.0, 0.25))
    raise RuntimeError("HTML request retry loop ended unexpectedly.")


def symbol_from_contract(contract: str) -> str:
    match = re.match(r"([A-Za-z]+)", contract)
    return match.group(1).upper() if match else ""


def fetch_main_contracts() -> list[dict[str, object]]:
    payload = get_json(
        MAIN_LIST_URL,
        {
            "orderBy": "",
            "sort": "",
            "pageSize": 999,
            "pageIndex": 0,
            "specificContract": "true",
            "platform": "zbPC",
            "field": LIST_FIELDS,
        },
    )
    contracts: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in payload.get("list", []):
        contract = str(item.get("dm", ""))
        if not contract or contract.endswith("F"):
            continue
        symbol = symbol_from_contract(contract)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        contracts.append(
            {
                "symbol": symbol,
                "variety": str(item.get("name", "")),
                "contract": contract,
                "market": int(item.get("sc", 0) or 0),
                "main_list_close": item.get("p", ""),
                "main_list_change_pct": item.get("zdf", ""),
            }
        )
    return contracts


def fetch_daily_quote(contract: dict[str, object], report_date: str) -> dict[str, object]:
    secid = f"{contract['market']}.{contract['contract']}"
    payload = get_json(
        KLINE_URL,
        {
            "secid": secid,
            "klt": 101,
            "fqt": 1,
            "beg": report_date,
            "end": report_date,
            "iscca": 1,
            "fields1": KLINE_FIELDS_1,
            "fields2": KLINE_FIELDS_2,
        },
    )
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        return {**contract, "status": "NO_REPORT_DATE_KLINE", "source_date": ""}

    values = str(klines[-1]).split(",")
    if len(values) < 10:
        return {**contract, "status": "MALFORMED_KLINE", "source_date": ""}

    return {
        **contract,
        "source_date": values[0],
        "open": values[1],
        "close": values[2],
        "high": values[3],
        "low": values[4],
        "volume": values[5],
        "turnover": values[6],
        "amplitude_pct": values[7],
        "change_pct": values[8],
        "change_amount": values[9],
        "status": "OK",
    }


def merge_existing_ok_rows(csv_path: Path, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not csv_path.exists():
        return rows
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        existing = {
            row.get("symbol", ""): row
            for row in csv.DictReader(handle)
            if valid_quote_row(row)
        }
    return [
        existing.get(str(row.get("symbol", "")), row) if row.get("status") != "OK" else row
        for row in rows
    ]


def parse_qhkch_overview(page: str, report_date: str) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    report_iso = datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d")
    market_match = re.search(r"let varietyMarketRows\s*=\s*(\[.*?\]);", page, re.S)
    if not market_match:
        return {}, []
    market_rows = json.loads(market_match.group(1))
    market = {
        str(row.get("symbol", "")).upper(): row
        for row in market_rows
        if row.get("data_date") == report_iso and row.get("data_complete")
    }
    by_variety = {str(row.get("variety", "")): row for row in market.values()}
    event_match = re.search(r'id="variety-key-events"(.*?)id="variety-sector-temperature"', page, re.S)
    events: list[dict[str, object]] = []
    if event_match:
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", event_match.group(1), re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
            if len(cells) < 6:
                continue
            plain = lambda value: " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", value)).split())
            variety = plain(cells[0])
            market_row = by_variety.get(variety, {})
            symbol = str(market_row.get("symbol", "")).upper()
            if not symbol or symbol in {"IC", "IF", "IH", "IM", "T", "TF", "TL", "TS", "CS"}:
                continue
            events.append({
                "variety": variety,
                "symbol": symbol,
                "events": [plain(value) for value in re.findall(r"<span[^>]*>(.*?)</span>", cells[1], re.S)],
                "priceChangePct": market_row.get("price_change_rate"),
                "openInterestChangePct": market_row.get("open_interest_change_rate"),
                "turnover": market_row.get("turnover"),
                "sector": plain(cells[5]),
                "sourceDate": report_iso,
                "source": "奇货可查商品概览",
                "sourceUrl": QHKCH_OVERVIEW_URL,
            })
    return market, events


def quote_from_qhkch(contract: dict[str, object], market_row: dict[str, object]) -> dict[str, object]:
    close = market_row.get("close_price")
    change_pct = market_row.get("price_change_rate")
    if not valid_quote_value(close) or not valid_quote_value(change_pct):
        return {**contract, "status": "NO_QHKCH_REPORT_DATE_QUOTE", "source_date": ""}
    previous_close = market_row.get("previous_close_price")
    return {
        **contract,
        "variety": market_row.get("variety") or contract.get("variety", ""),
        "source_date": market_row.get("data_date", ""),
        "close": close,
        "change_pct": change_pct,
        "change_amount": float(close) - float(previous_close) if valid_quote_value(previous_close) else "",
        "turnover": market_row.get("turnover", ""),
        "source": "奇货可查商品主连",
        "source_url": QHKCH_OVERVIEW_URL,
        "status": "OK",
    }


def parse_qhkch_position_page(page: str, symbol: str) -> list[dict[str, object]]:
    contract_match = re.search(r'<option value="([^"]+)"\s+selected>', page, re.S)
    contract = contract_match.group(1) if contract_match else ""
    brokers: dict[str, dict[str, object]] = {}

    def integer(value: str) -> int:
        cleaned = re.sub(r"[^0-9+-]", "", value)
        return int(cleaned) if cleaned not in {"", "+", "-"} else 0

    def plain(value: str) -> str:
        return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", value)).split())

    for side, row_html in re.findall(r'<tr id="variety_position_(buy|ss)_tr_\d+"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r'<td class="([^"]*)"[^>]*>(.*?)</td>', row_html, re.S)
        broker_cell = next((body for classes, body in cells if "sort-broker" in classes.split()), "")
        broker_match = re.search(r"broker=([^&'\"]+)", broker_cell)
        broker = unquote_plus(broker_match.group(1)) if broker_match else plain(broker_cell)
        if not broker:
            continue
        item = brokers.setdefault(broker, {"symbol": symbol, "contract": contract, "broker": broker, "long_pos": 0, "long_chg": 0, "short_pos": 0, "short_chg": 0})
        values = {name: integer(plain(body)) for classes, body in cells for name in classes.split() if name.startswith("sort-")}
        if side == "buy":
            item["long_pos"] = values.get("sort-buy", 0)
            item["long_chg"] = values.get("sort-buy_chge", 0)
        else:
            item["short_pos"] = values.get("sort-ss", 0)
            item["short_chg"] = values.get("sort-ss_chge", 0)

    result = []
    for item in brokers.values():
        long_pos = int(item["long_pos"])
        short_pos = int(item["short_pos"])
        long_chg = int(item["long_chg"])
        short_chg = int(item["short_chg"])
        result.append({
            **item,
            "net_pos": long_pos - short_pos,
            "flow_score": long_chg - short_chg,
            "add_long": max(long_chg, 0),
            "reduce_long": max(-long_chg, 0),
            "add_short": max(short_chg, 0),
            "reduce_short": max(-short_chg, 0),
        })
    return result


def fetch_qhkch_position_rows(market: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    targets = {
        symbol: row for symbol, row in market.items()
        if symbol not in {"IC", "IF", "IH", "IM", "T", "TF", "TL", "TS", "CS"} and row.get("url")
    }
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(get_text, urljoin(QHKCH_OVERVIEW_URL, str(row["url"]))): symbol
            for symbol, row in targets.items()
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows.extend(parse_qhkch_position_page(future.result(), symbol))
            except (HTTPError, URLError, TimeoutError, http.client.RemoteDisconnected, UnicodeDecodeError):
                continue
    return rows


def main() -> None:
    report_date = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
    if not re.fullmatch(r"\d{8}", report_date):
        raise SystemExit("REPORT_DATE must use YYYYMMDD.")

    contracts = fetch_main_contracts()
    beijing_today = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    events: list[dict[str, object]] = []
    position_rows: list[dict[str, object]] = []
    try:
        market, events = parse_qhkch_overview(get_text(QHKCH_OVERVIEW_URL), report_date)
    except (HTTPError, URLError, TimeoutError, http.client.RemoteDisconnected, UnicodeDecodeError, json.JSONDecodeError):
        market = {}
    if market:
        position_rows = fetch_qhkch_position_rows(market)
    rows = [quote_from_qhkch(contract, market.get(str(contract["symbol"]), {})) for contract in contracts]
    missing = [row for row in rows if not valid_quote_row(row)]
    if missing:
        replacements: dict[str, dict[str, object]] = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_daily_quote, row, report_date): row for row in missing}
            for future in as_completed(futures):
                row = futures[future]
                try:
                    replacements[str(row["symbol"])] = future.result()
                except Exception as exc:
                    replacements[str(row["symbol"])] = {**row, "status": f"ERROR:{type(exc).__name__}", "source_date": ""}
        rows = [replacements.get(str(row["symbol"]), row) for row in rows]

    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / f"eastmoney_main_quotes_{report_date}.csv"
    if report_date != beijing_today:
        rows = merge_existing_ok_rows(csv_path, rows)
    rows.sort(key=lambda row: str(row.get("symbol", "")))
    contracts_by_symbol = {str(row.get("symbol", "")): str(row.get("contract", "")) for row in position_rows if row.get("contract")}
    rows = [{**row, "contract": contracts_by_symbol.get(str(row.get("symbol", "")), row.get("contract", ""))} for row in rows]
    fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    fieldnames = [
        "report_date", "source_date", "symbol", "variety", "contract", "market", "open", "close", "high", "low",
        "volume", "turnover", "amplitude_pct", "change_pct", "change_amount", "status", "source", "source_url", "fetched_at",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "report_date": report_date,
                    "source": row.get("source", "东方财富期货主力日线"),
                    "source_url": row.get("source_url", SOURCE_PAGE),
                    "fetched_at": fetched_at,
                }
            )

    ok_rows = [row for row in rows if valid_quote_row(row)]
    status = {
        "report_date": report_date,
        "source": "东方财富期货主力日线",
        "source_url": SOURCE_PAGE,
        "fetched_at": fetched_at,
        "main_contracts": len(contracts),
        "matched_report_date": len(ok_rows),
        "missing": [row.get("symbol") for row in rows if not valid_quote_row(row)],
    }
    status_path = data_dir / f"eastmoney_main_quotes_status_{report_date}.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    overview_path = data_dir / f"qhkch_variety_overview_{report_date}.json"
    overview_path.write_text(json.dumps({"reportDate": report_date, "events": events}, ensure_ascii=False, indent=2), encoding="utf-8")
    position_path = data_dir / f"qhkch_main_position_rows_{report_date}.csv"
    position_fields = ["symbol", "contract", "broker", "long_pos", "long_chg", "short_pos", "short_chg", "net_pos", "flow_score", "add_long", "reduce_long", "add_short", "reduce_short"]
    with position_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=position_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(position_rows)
    print(f"Eastmoney main quotes: {csv_path}")
    print(f"Matched report-date klines: {len(ok_rows)}/{len(contracts)}")


if __name__ == "__main__":
    main()
