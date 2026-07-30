"""Fetch report-date closing quotes for Eastmoney domestic main futures contracts."""

from __future__ import annotations

import csv
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
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PAGE = "https://qhweb.eastmoney.com/quote/zhuli"
MAIN_LIST_URL = "https://futsseapi.eastmoney.com/list/trans/block/risk/mk0830"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
USER_AGENT = "Mozilla/5.0"
LIST_FIELDS = "name,p,zdf,dm,sc,uid,zsjd"
KLINE_FIELDS_1 = "f1,f2,f3,f4,f5,f6,f7,f8"
KLINE_FIELDS_2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
MAX_WORKERS = 2
MAX_ATTEMPTS = 4


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
            if row.get("status") == "OK"
        }
    return [
        existing.get(str(row.get("symbol", "")), row) if row.get("status") != "OK" else row
        for row in rows
    ]


def quote_from_main_list(contract: dict[str, object], report_date: str) -> dict[str, object]:
    close = contract.get("main_list_close")
    change_pct = contract.get("main_list_change_pct")
    if close in ("", None) or change_pct in ("", None):
        return {**contract, "status": "NO_MAIN_LIST_QUOTE", "source_date": ""}
    return {
        **contract,
        "source_date": datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "close": close,
        "change_pct": change_pct,
        "status": "OK",
    }


def main() -> None:
    report_date = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
    if not re.fullmatch(r"\d{8}", report_date):
        raise SystemExit("REPORT_DATE must use YYYYMMDD.")

    contracts = fetch_main_contracts()
    beijing_today = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    if report_date == beijing_today:
        rows = [quote_from_main_list(contract, report_date) for contract in contracts]
    else:
        rows = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_daily_quote, contract, report_date): contract for contract in contracts}
            for future in as_completed(futures):
                contract = futures[future]
                try:
                    rows.append(future.result())
                except Exception as exc:
                    rows.append({**contract, "status": f"ERROR:{type(exc).__name__}", "source_date": ""})

    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / f"eastmoney_main_quotes_{report_date}.csv"
    rows = merge_existing_ok_rows(csv_path, rows)
    rows.sort(key=lambda row: str(row.get("symbol", "")))
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
                    "source": "东方财富期货主力日线",
                    "source_url": SOURCE_PAGE,
                    "fetched_at": fetched_at,
                }
            )

    ok_rows = [row for row in rows if row.get("status") == "OK"]
    status = {
        "report_date": report_date,
        "source": "东方财富期货主力日线",
        "source_url": SOURCE_PAGE,
        "fetched_at": fetched_at,
        "main_contracts": len(contracts),
        "matched_report_date": len(ok_rows),
        "missing": [row.get("symbol") for row in rows if row.get("status") != "OK"],
    }
    status_path = data_dir / f"eastmoney_main_quotes_status_{report_date}.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Eastmoney main quotes: {csv_path}")
    print(f"Matched report-date klines: {len(ok_rows)}/{len(contracts)}")


if __name__ == "__main__":
    main()
