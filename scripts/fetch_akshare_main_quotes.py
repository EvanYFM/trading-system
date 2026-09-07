from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import akshare as ak

ROOT = Path(__file__).resolve().parents[1]
REPORT_DATE = os.environ.get("REPORT_DATE", datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d"))
REPORT_ISO = f"{REPORT_DATE[:4]}-{REPORT_DATE[4:6]}-{REPORT_DATE[6:]}"
INPUT = ROOT / "output" / f"margin_weighted_seat_report_{REPORT_DATE}" / "data" / "institutional_amount_resonance.csv"
OUTPUT = ROOT / "data" / f"akshare_main_quotes_{REPORT_DATE}.csv"
STATUS = ROOT / "data" / f"akshare_main_quotes_{REPORT_DATE}.status.json"


def pct(current: float, previous: float) -> float | None:
    return None if not previous else (current / previous - 1) * 100


def akshare_contract(contract: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)(\d{3})", contract)
    return f"{match.group(1)}2{match.group(2)}" if match else contract


def main() -> None:
    contracts = []
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            contract = row.get("domestic_margin_contract") or row.get("foreign_margin_contract") or row.get("family_margin_contract")
            contracts.append((row["symbol"], row["variety"], contract))

    rows, failures = [], []
    retrieved_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    for symbol, variety, contract in contracts:
        try:
            frame = ak.futures_zh_daily_sina(symbol=akshare_contract(contract).upper())
            frame["date"] = frame["date"].astype(str)
            index = frame.index[frame["date"] == REPORT_ISO].tolist()
            if not index:
                raise ValueError("report date missing")
            pos = frame.index.get_loc(index[-1])
            current = frame.iloc[pos]
            close = float(current["close"])
            prior_settle = float(frame.iloc[pos - 1]["settle"])
            prior_hold = int(frame.iloc[pos - 1]["hold"])
            current_hold = int(current["hold"])
            row = {
                "report_date": REPORT_DATE, "source_date": REPORT_ISO, "symbol": symbol, "variety": variety,
                "contract": contract, "close": close, "change_pct": pct(close, prior_settle),
                "return_5d": pct(close, float(frame.iloc[pos - 5]["close"])) if pos >= 5 else None,
                "return_10d": pct(close, float(frame.iloc[pos - 10]["close"])) if pos >= 10 else None,
                "return_20d": pct(close, float(frame.iloc[pos - 20]["close"])) if pos >= 20 else None,
                "return_30d": pct(close, float(frame.iloc[pos - 30]["close"])) if pos >= 30 else None,
                "monthly_return": pct(close, float(frame.iloc[frame.index[frame["date"] < REPORT_ISO][-1]]["close"])) if REPORT_ISO.endswith("-01") else None,
                "volume": int(current["volume"]), "open_interest": current_hold,
                "open_interest_change": current_hold - prior_hold,
                "open_interest_change_pct": pct(current_hold, prior_hold),
                "settle": float(current["settle"]), "retrieved_at": retrieved_at,
                "source": "AKShare futures_zh_daily_sina", "status": "OK",
            }
            month_rows = frame[(frame["date"] < REPORT_ISO) & (frame["date"].str[:7] < REPORT_ISO[:7])]
            if not month_rows.empty:
                row["monthly_return"] = pct(close, float(month_rows.iloc[-1]["close"]))
            rows.append(row)
        except Exception as exc:
            failures.append({"symbol": symbol, "contract": contract, "error": str(exc)})

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(rows)
    STATUS.write_text(json.dumps({"report_date": REPORT_DATE, "retrieved_at": retrieved_at, "ok": len(rows), "failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"AKShare daily: {OUTPUT} ({len(rows)}/{len(contracts)})")
    if failures:
        print(json.dumps(failures, ensure_ascii=False))


if __name__ == "__main__":
    assert akshare_contract("MA610") == "MA2610"
    main()
