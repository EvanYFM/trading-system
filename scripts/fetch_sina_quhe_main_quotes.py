"""Fetch report-day main futures quotes from Quhe, validated by Sina daily bars."""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from fetch_eastmoney_technical_snapshot import fetch_sina_daily_history


ROOT = Path(__file__).resolve().parents[1]
QUHE_PAGE = "https://m.quheqihuo.com/quote/zhuli.html"
QUHE_API = "https://api.jijinhao.com/quoteCenter/realTime.htm?codes="
ALIASES = {
    "PP": "聚丙烯", "L": "塑料", "V": "PVC", "BU": "石油沥青", "FU": "燃料油",
    "PG": "液化石油气", "SM": "锰硅", "OI": "菜籽油", "LU": "低硫燃料油",
    "RM": "菜籽粕（菜粕）", "RU": "橡胶",
}


def fetch_text(url: str, referer: str = QUHE_PAGE) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": referer})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def quhe_catalog(html: str) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for block in re.findall(r"<dd\b.*?</dd>", html, re.S):
        title = re.search(r'title="([^"]+)"', block)
        code = re.search(r'class="JO_(\d+)_q63', block)
        if title and code:
            catalog[title.group(1).strip()] = f"JO_{code.group(1)}"
    return catalog


def quhe_quotes(codes: list[str]) -> dict[str, dict[str, object]]:
    quotes: dict[str, dict[str, object]] = {}
    for start in range(0, len(codes), 40):
        text = fetch_text(QUHE_API + ",".join(codes[start : start + 40]))
        match = re.search(r"var\s+quote_json\s*=\s*(\{.*\})\s*;?", text, re.S)
        if not match:
            raise ValueError("Quhe quote response is invalid")
        payload = json.loads(match.group(1))
        quotes.update({code: row for code, row in payload.items() if code.startswith("JO_") and isinstance(row, dict)})
    return quotes


def normalize_contract(contract: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)(\d{3})", contract.strip())
    return f"{match.group(1)}2{match.group(2)}" if match else contract


def sina_realtime(contract: str) -> dict[str, object]:
    symbol = normalize_contract(contract).upper()
    text = fetch_text(f"https://hq.sinajs.cn/list=nf_{symbol}", "https://finance.sina.com.cn/futuremarket/")
    match = re.search(r'="([^"]*)"', text)
    fields = match.group(1).split(",") if match else []
    if len(fields) < 18:
        return {}
    close = float(fields[5] or 0)
    settlement = float(fields[10] or 0)
    return {
        "date": fields[17], "open": fields[2], "high": fields[3], "low": fields[4], "close": close,
        "change_pct": (close / settlement - 1) * 100 if settlement else "", "change_amount": close - settlement if settlement else "",
        "volume": fields[14], "open_interest": fields[13],
    }


def report_contracts(report_date: str) -> list[dict[str, str]]:
    path = ROOT / "output" / f"margin_weighted_seat_report_{report_date}" / "data" / "institutional_amount_resonance.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "symbol": row["symbol"].upper(),
            "variety": row["variety"],
            "contract": row.get("domestic_margin_contract") or row.get("foreign_margin_contract") or row.get("family_margin_contract") or "",
        }
        for row in rows
        if row.get("symbol")
    ]


def build(report_date: str) -> list[dict[str, object]]:
    iso_date = datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d")
    contracts = report_contracts(report_date)
    catalog = quhe_catalog(fetch_text(QUHE_PAGE))
    selected = {
        row["symbol"]: catalog.get(row["variety"]) or catalog.get(ALIASES.get(row["symbol"], ""))
        for row in contracts
    }
    live = quhe_quotes(sorted({code for code in selected.values() if code}))
    output: list[dict[str, object]] = []
    for contract in contracts:
        symbol = contract["symbol"]
        code = selected.get(symbol)
        quhe = live.get(code or "", {})
        try:
            sina_rows = fetch_sina_daily_history(normalize_contract(contract["contract"]), report_date)
            sina = next(row for row in reversed(sina_rows) if str(row["date"]) == iso_date)
        except (OSError, StopIteration, ValueError):
            sina = {}
        try:
            realtime = sina_realtime(contract["contract"])
        except (OSError, ValueError):
            realtime = {}
        quhe_date = datetime.fromtimestamp(float(quhe.get("time", 0)) / 1000).astimezone().strftime("%Y-%m-%d") if quhe.get("time") else ""
        close = float(quhe.get("q63", 0) or 0)
        sina_close = float(sina.get("close", 0) or 0)
        agreed = bool(close and sina_close and quhe_date == iso_date and abs(close - sina_close) <= max(0.01, abs(close) * 0.0002))
        use_quhe = bool(close and quhe_date == iso_date)
        fallback_ok = bool(realtime.get("close") and realtime.get("date") == iso_date)
        output.append(
            {
                **contract,
                "contract": str(quhe.get("showCode", "")) if use_quhe else normalize_contract(contract["contract"]),
                "market": "",
                "source_date": quhe_date if use_quhe else realtime.get("date", ""),
                "open": quhe.get("q1", "") if use_quhe else realtime.get("open", ""),
                "high": quhe.get("q3", "") if use_quhe else realtime.get("high", ""),
                "low": quhe.get("q4", "") if use_quhe else realtime.get("low", ""),
                "close": close if use_quhe else realtime.get("close", ""),
                "change_pct": quhe.get("q80", "") if use_quhe else realtime.get("change_pct", ""),
                "change_amount": quhe.get("q70", "") if use_quhe else realtime.get("change_amount", ""),
                "volume": quhe.get("q60", "") if use_quhe else realtime.get("volume", ""),
                "turnover": quhe.get("q61", ""),
                "amplitude_pct": "",
                "source": "曲合期货主力行情（涨跌按前结算）" if use_quhe else "新浪财经主力合约实时收盘（涨跌按前结算）",
                "source_url": QUHE_PAGE if use_quhe else "https://finance.sina.com.cn/futuremarket/",
                "validation_status": "SINA_CLOSE_AGREES" if agreed else "QUHE_MAIN_DIFFERS_FROM_SEAT_CONTRACT" if use_quhe else "SINA_ONLY",
                "sina_close": sina_close or "",
                "quhe_code": code or "",
                "status": "OK" if use_quhe or fallback_ok else "MISSING_OR_CONFLICT",
            }
        )
    return output


def main() -> None:
    report_date = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
    rows = build(report_date)
    path = ROOT / "data" / f"sina_quhe_main_quotes_{report_date}.csv"
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Quote file: {path}")
    print(f"Validated: {sum(row['status'] == 'OK' for row in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
