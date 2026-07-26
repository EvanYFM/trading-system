"""Fetch basis, warehouse receipts, and cash-index closes for the dashboard."""

from __future__ import annotations

import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lxml import html


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "output"
DATA_DIR = ROOT / "data"
USER_AGENT = "Mozilla/5.0"
EASTMONEY_DATA_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_INVENTORY_PAGE = "https://data.eastmoney.com/ifdata/kcsj.html"
EASTMONEY_QUOTE_PAGE = "https://quote.eastmoney.com/"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={symbols}"
BASIS_PAGE = "https://www.100ppi.com/sf/day-{date}.html"
CORE_SYMBOLS = {"AU", "AG", "SN", "LC", "FU", "JM", "FG", "SA", "AO", "SH", "M", "JD", "LH"}
BASIS_NAMES = {
    "黄金": "AU",
    "白银": "AG",
    "锡": "SN",
    "碳酸锂": "LC",
    "燃料油": "FU",
    "焦煤": "JM",
    "玻璃": "FG",
    "纯碱": "SA",
    "氧化铝": "AO",
    "烧碱": "SH",
    "豆粕": "M",
    "鸡蛋": "JD",
    "生猪": "LH",
}
INVENTORY_CODES = {
    "AU": "AU",
    "AG": "AG",
    "SN": "SN",
    "LC": "lc",
    "FU": "FU",
    "JM": "JM",
    "FG": "FG",
    "SA": "SA",
    "AO": "AO",
    "SH": "SH",
    "M": "M",
    "JD": "JD",
    "LH": "LH",
}
INDEX_DEFINITIONS = {
    "IH": ("上证50", "1.000016"),
    "IF": ("沪深300", "1.000300"),
    "IC": ("中证500", "1.000905"),
    "IM": ("中证1000", "1.000852"),
    "STAR50": ("科创50", "1.000688"),
    "GEM50": ("创业板50", "0.399673"),
}
TENCENT_INDEX_CODES = {
    "IH": "sh000016",
    "IF": "sh000300",
    "IC": "sh000905",
    "IM": "sh000852",
    "STAR50": "sh000688",
    "GEM50": "sz399673",
}


def get_bytes(url: str, *, referer: str = "", attempts: int = 3) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"request failed: {type(last_error).__name__}") from last_error


def get_json(url: str, params: dict[str, object], *, referer: str) -> dict:
    payload = get_bytes(f"{url}?{urlencode(params)}", referer=referer)
    return json.loads(payload.decode("utf-8"))


def dashboard_dates(report_date: str) -> list[str]:
    institutional = {
        path.name.rsplit("_", 1)[-1]
        for path in OUTPUT_ROOT.glob("institutional_seat_report_*")
        if re.fullmatch(r"\d{8}", path.name.rsplit("_", 1)[-1])
    }
    margin = {
        path.name.rsplit("_", 1)[-1]
        for path in OUTPUT_ROOT.glob("margin_weighted_seat_report_*")
        if re.fullmatch(r"\d{8}", path.name.rsplit("_", 1)[-1])
    }
    return sorted(date for date in institutional & margin if date <= report_date)[-30:]


def parse_number(value: object) -> float | None:
    text = str(value or "").replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def fetch_basis(date: str) -> list[dict[str, object]]:
    iso_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    url = BASIS_PAGE.format(date=iso_date)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    body = get_bytes(url)
    challenge = re.search(rb'_0x2 = "([a-f0-9]+)"', body)
    if challenge:
        headers["Cookie"] = f"HW_CHECK={challenge.group(1).decode()}"
        request = Request(url, headers=headers)
        with urlopen(request, timeout=30) as response:
            body = response.read()
    tree = html.fromstring(body)
    rows: list[dict[str, object]] = []
    for table_row in tree.xpath("//table[@id='fdata']/tr"):
        cells = table_row.xpath("./td")
        if len(cells) < 8:
            continue
        name = " ".join(cells[0].text_content().split())
        symbol = BASIS_NAMES.get(name)
        if not symbol:
            continue
        main_text = [part.strip() for part in cells[7].xpath(".//text()") if part.strip()]
        basis = parse_number(main_text[0] if main_text else "")
        basis_pct = parse_number(main_text[1] if len(main_text) > 1 else "")
        rows.append(
            {
                "source_date": iso_date,
                "symbol": symbol,
                "variety": name,
                "spot_price": parse_number(cells[1].text_content()),
                "main_contract": " ".join(cells[5].text_content().split()),
                "main_price": parse_number(cells[6].text_content()),
                "basis": basis,
                "basis_pct": basis_pct,
                "basis_convention": "现货价-主力期货价",
                "status": "OK" if basis is not None else "PARSE_ERROR",
                "source": "生意社期现基差表",
                "source_url": url,
            }
        )
    return rows


def fetch_inventory(symbol: str, product_code: str, start_date: str, report_date: str) -> list[dict[str, object]]:
    payload = get_json(
        EASTMONEY_DATA_URL,
        {
            "reportName": "RPT_FUTU_STOCKDATA",
            "columns": "SECURITY_CODE,TRADE_DATE,ON_WARRANT_NUM,ADDCHANGE",
            "filter": f'(SECURITY_CODE="{product_code}")(TRADE_DATE>=\'{start_date}\')',
            "pageNumber": "1",
            "pageSize": "500",
            "sortTypes": "-1",
            "sortColumns": "TRADE_DATE",
            "source": "WEB",
            "client": "WEB",
        },
        referer=EASTMONEY_INVENTORY_PAGE,
    )
    result = []
    for row in (payload.get("result") or {}).get("data") or []:
        source_date = str(row.get("TRADE_DATE", ""))[:10]
        compact = source_date.replace("-", "")
        if not source_date or compact > report_date:
            continue
        result.append(
            {
                "source_date": source_date,
                "symbol": symbol,
                "warehouse_receipt": parse_number(row.get("ON_WARRANT_NUM")),
                "change": parse_number(row.get("ADDCHANGE")),
                "unit": "交易所披露单位",
                "status": "OK",
                "source": "东方财富期货库存数据",
                "source_url": EASTMONEY_INVENTORY_PAGE,
            }
        )
    return result


def fetch_index(symbol: str, name: str, secid: str, start_date: str, report_date: str) -> list[dict[str, object]]:
    payload = get_json(
        EASTMONEY_KLINE_URL,
        {
            "secid": secid,
            "klt": 101,
            "fqt": 1,
            "beg": start_date,
            "end": report_date,
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        },
        referer=EASTMONEY_QUOTE_PAGE,
    )
    rows = []
    for line in (payload.get("data") or {}).get("klines") or []:
        values = str(line).split(",")
        if len(values) < 10:
            continue
        rows.append(
            {
                "source_date": values[0],
                "symbol": symbol,
                "variety": name,
                "close": parse_number(values[2]),
                "change_pct": parse_number(values[8]),
                "status": "OK",
                "source": "东方财富指数日线",
                "source_url": EASTMONEY_QUOTE_PAGE,
            }
        )
    return rows


def fetch_index_quotes_tencent(report_date: str) -> list[dict[str, object]]:
    url = TENCENT_QUOTE_URL.format(symbols=",".join(TENCENT_INDEX_CODES.values()))
    body = get_bytes(url, referer="https://gu.qq.com/").decode("gbk", errors="replace")
    reverse = {code: symbol for symbol, code in TENCENT_INDEX_CODES.items()}
    rows: list[dict[str, object]] = []
    for code, payload in re.findall(r'v_([a-z0-9]+)="([^"]*)"', body):
        symbol = reverse.get(code)
        values = payload.split("~")
        if not symbol or len(values) < 33:
            continue
        source_date = values[30][:8]
        if source_date != report_date:
            continue
        name = INDEX_DEFINITIONS[symbol][0]
        rows.append(
            {
                "source_date": f"{source_date[:4]}-{source_date[4:6]}-{source_date[6:]}",
                "symbol": symbol,
                "variety": name,
                "close": parse_number(values[3]),
                "change_pct": parse_number(values[32]),
                "status": "OK",
                "source": "腾讯证券指数行情",
                "source_url": "https://gu.qq.com/",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    report_date = os.environ.get("REPORT_DATE", datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d"))
    if not re.fullmatch(r"\d{8}", report_date):
        raise SystemExit("REPORT_DATE must use YYYYMMDD.")
    dates = dashboard_dates(report_date)
    if not dates:
        dates = [report_date]
    start_date = f"{dates[0][:4]}-{dates[0][4:6]}-{dates[0][6:]}"
    statuses: dict[str, object] = {"report_date": report_date, "basis_failed_dates": [], "inventory_failed_symbols": [], "index_failed_symbols": []}

    basis_rows: list[dict[str, object]] = []
    for date in dates:
        try:
            basis_rows.extend(fetch_basis(date))
        except Exception as exc:
            statuses["basis_failed_dates"].append({"date": date, "error": type(exc).__name__})

    inventory_rows: list[dict[str, object]] = []
    for symbol, product_code in INVENTORY_CODES.items():
        try:
            inventory_rows.extend(fetch_inventory(symbol, product_code, start_date, report_date))
        except Exception as exc:
            statuses["inventory_failed_symbols"].append({"symbol": symbol, "error": type(exc).__name__})

    index_rows: list[dict[str, object]] = []
    for symbol, (name, secid) in INDEX_DEFINITIONS.items():
        try:
            index_rows.extend(fetch_index(symbol, name, secid, dates[0], report_date))
        except Exception as exc:
            statuses["index_failed_symbols"].append({"symbol": symbol, "error": type(exc).__name__})
    if not index_rows:
        try:
            index_rows = fetch_index_quotes_tencent(report_date)
            statuses["index_fallback"] = "腾讯证券指数行情"
        except Exception as exc:
            statuses["index_fallback"] = f"FAILED:{type(exc).__name__}"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        DATA_DIR / f"futures_basis_history_{report_date}.csv",
        sorted(basis_rows, key=lambda row: (str(row["symbol"]), str(row["source_date"]))),
        ["source_date", "symbol", "variety", "spot_price", "main_contract", "main_price", "basis", "basis_pct", "basis_convention", "status", "source", "source_url"],
    )
    write_csv(
        DATA_DIR / f"eastmoney_warehouse_receipts_{report_date}.csv",
        sorted(inventory_rows, key=lambda row: (str(row["symbol"]), str(row["source_date"]))),
        ["source_date", "symbol", "warehouse_receipt", "change", "unit", "status", "source", "source_url"],
    )
    write_csv(
        DATA_DIR / f"eastmoney_index_quotes_{report_date}.csv",
        sorted(index_rows, key=lambda row: (str(row["symbol"]), str(row["source_date"]))),
        ["source_date", "symbol", "variety", "close", "change_pct", "status", "source", "source_url"],
    )
    statuses.update({"basis_rows": len(basis_rows), "inventory_rows": len(inventory_rows), "index_rows": len(index_rows)})
    (DATA_DIR / f"research_dashboard_market_context_status_{report_date}.json").write_text(
        json.dumps(statuses, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Market context: basis={len(basis_rows)}, warehouse={len(inventory_rows)}, indices={len(index_rows)}")


if __name__ == "__main__":
    main()
