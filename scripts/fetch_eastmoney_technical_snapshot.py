"""Build a compact technical snapshot from Eastmoney main-contract daily bars."""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from fetch_eastmoney_main_quotes import (
    KLINE_FIELDS_1,
    KLINE_FIELDS_2,
    KLINE_URL,
    SOURCE_PAGE,
    fetch_main_contracts,
    get_json,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOLS = ("AG",)


def value(text: object) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def mean(values: list[float], period: int) -> float | None:
    return statistics.fmean(values[-period:]) if len(values) >= period else None


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    factor = 2 / (period + 1)
    result = [values[0]]
    for item in values[1:]:
        result.append(item * factor + result[-1] * (1 - factor))
    return result


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = statistics.fmean(gains[:period])
    avg_loss = statistics.fmean(losses[:period])
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    relative = avg_gain / avg_loss
    return 100 - 100 / (1 + relative)


def atr(rows: list[dict[str, float | str]], period: int = 14) -> float | None:
    if len(rows) <= period:
        return None
    true_ranges: list[float] = []
    for index, row in enumerate(rows):
        high = float(row["high"])
        low = float(row["low"])
        if index == 0:
            true_ranges.append(high - low)
            continue
        previous_close = float(rows[index - 1]["close"])
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    current = statistics.fmean(true_ranges[1 : period + 1])
    for item in true_ranges[period + 1 :]:
        current = (current * (period - 1) + item) / period
    return current


def pct_change(values: list[float], period: int) -> float | None:
    if len(values) <= period or values[-period - 1] == 0:
        return None
    return (values[-1] / values[-period - 1] - 1) * 100


def parse_klines(klines: list[object]) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for raw in klines:
        fields = str(raw).split(",")
        if len(fields) < 11:
            continue
        rows.append(
            {
                "date": fields[0],
                "open": value(fields[1]),
                "close": value(fields[2]),
                "high": value(fields[3]),
                "low": value(fields[4]),
                "volume": value(fields[5]),
                "turnover": value(fields[6]),
                "amplitude_pct": value(fields[7]),
                "change_pct": value(fields[8]),
                "change_amount": value(fields[9]),
                "turnover_rate": value(fields[10]),
            }
        )
    return rows


def read_cached_history(symbol: str, report_date: str) -> list[dict[str, float | str]]:
    path = ROOT / "data" / f"eastmoney_technical_history_{symbol}_{report_date}.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key: value(raw) if key != "date" else raw for key, raw in row.items()}
            for row in csv.DictReader(handle)
        ]


def reconcile_latest_quote(rows: list[dict[str, float | str]], symbol: str, report_date: str) -> bool:
    path = ROOT / "data" / f"eastmoney_main_quotes_{report_date}.csv"
    if not rows or not path.exists():
        return False
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        quote = next((row for row in csv.DictReader(handle) if row.get("symbol", "").upper() == symbol), None)
    if not quote or quote.get("status") != "OK" or quote.get("source_date", "").replace("-", "") != report_date:
        return False
    latest = rows[-1]
    if str(latest.get("date", "")).replace("-", "") != report_date:
        return False
    field_map = {
        "open": "open",
        "close": "close",
        "high": "high",
        "low": "low",
        "volume": "volume",
        "turnover": "turnover",
        "amplitude_pct": "amplitude_pct",
        "change_pct": "change_pct",
        "change_amount": "change_amount",
    }
    for target, source in field_map.items():
        latest[target] = value(quote.get(source))
    return True


def build_snapshot(contract: dict[str, object], report_date: str) -> tuple[dict[str, object], list[dict[str, float | str]]]:
    end_date = datetime.strptime(report_date, "%Y%m%d")
    begin_date = (end_date - timedelta(days=300)).strftime("%Y%m%d")
    secid = f"{contract['market']}.{contract['contract']}"
    history_status = "LIVE_KLINE"
    try:
        payload = get_json(
            KLINE_URL,
            {
                "secid": secid,
                "klt": 101,
                "fqt": 1,
                "beg": begin_date,
                "end": report_date,
                "iscca": 1,
                "fields1": KLINE_FIELDS_1,
                "fields2": KLINE_FIELDS_2,
            },
        )
        rows = parse_klines(((payload.get("data") or {}).get("klines") or []))
    except OSError:
        rows = read_cached_history(str(contract["symbol"]), report_date)
        if not rows:
            raise
        history_status = "CACHED_HISTORY"
    if reconcile_latest_quote(rows, str(contract["symbol"]), report_date):
        history_status += "+FINAL_QUOTE"
    if len(rows) < 20:
        return {
            **contract,
            "reportDate": report_date,
            "status": "INSUFFICIENT_HISTORY",
            "barCount": len(rows),
            "source": "东方财富期货主力合约日线",
            "sourceUrl": SOURCE_PAGE,
        }, rows

    closes = [float(row["close"]) for row in rows]
    volumes = [float(row["volume"]) for row in rows]
    ma5 = mean(closes, 5)
    ma10 = mean(closes, 10)
    ma20 = mean(closes, 20)
    ma60 = mean(closes, 60)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif_series = [short - long for short, long in zip(ema12, ema26)]
    dea_series = ema(dif_series, 9)
    dif = dif_series[-1]
    dea = dea_series[-1]
    macd_hist = (dif - dea) * 2
    rsi14 = rsi(closes)
    atr14 = atr(rows)
    average20 = ma20 or closes[-1]
    deviation20 = statistics.pstdev(closes[-20:])
    boll_upper = average20 + 2 * deviation20
    boll_lower = average20 - 2 * deviation20
    band_width = boll_upper - boll_lower
    boll_position = (closes[-1] - boll_lower) / band_width * 100 if band_width else 50.0
    high20 = max(float(row["high"]) for row in rows[-20:])
    low20 = min(float(row["low"]) for row in rows[-20:])
    high60 = max(float(row["high"]) for row in rows[-60:]) if len(rows) >= 60 else None
    low60 = min(float(row["low"]) for row in rows[-60:]) if len(rows) >= 60 else None
    volume5 = mean(volumes, 5)
    volume20 = mean(volumes, 20)
    volume_ratio = volume5 / volume20 if volume5 is not None and volume20 else None

    structure_score = 0
    if ma20 is not None:
        structure_score += 1 if closes[-1] > ma20 else -1
    if ma60 is not None:
        structure_score += 1 if closes[-1] > ma60 else -1
        structure_score += 1 if ma20 is not None and ma20 > ma60 else -1
    momentum_score = (1 if dif > dea else -1) + (1 if (rsi14 or 50) > 55 else -1 if (rsi14 or 50) < 45 else 0)
    trigger_score = (1 if ma5 is not None and closes[-1] > ma5 else -1) + (1 if ma10 is not None and closes[-1] > ma10 else -1)
    total_score = structure_score + momentum_score + trigger_score
    if total_score >= 4:
        bias = "偏多"
    elif total_score <= -4:
        bias = "偏空"
    else:
        bias = "震荡"

    latest = rows[-1]
    return {
        **contract,
        "reportDate": report_date,
        "sourceDate": str(latest["date"]),
        "status": "OK" if str(latest["date"]).replace("-", "") == report_date else "STALE",
        "source": "东方财富期货主力合约日线",
        "sourceUrl": SOURCE_PAGE,
        "historyStatus": history_status,
        "barCount": len(rows),
        "startDate": rows[0]["date"],
        "endDate": rows[-1]["date"],
        "close": closes[-1],
        "changePct": float(latest["change_pct"]),
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "return5": pct_change(closes, 5),
        "return20": pct_change(closes, 20),
        "return60": pct_change(closes, 60),
        "rsi14": rsi14,
        "macdDif": dif,
        "macdDea": dea,
        "macdHist": macd_hist,
        "atr14": atr14,
        "atrPct": atr14 / closes[-1] * 100 if atr14 and closes[-1] else None,
        "bollUpper": boll_upper,
        "bollMiddle": average20,
        "bollLower": boll_lower,
        "bollPosition": boll_position,
        "high20": high20,
        "low20": low20,
        "high60": high60,
        "low60": low60,
        "volumeRatio5To20": volume_ratio,
        "structureScore": structure_score,
        "momentumScore": momentum_score,
        "triggerScore": trigger_score,
        "score": total_score,
        "bias": bias,
        "method": "价格结构、动量与短线触发三层规则；技术面仅作为执行层验证",
        "limitations": "当前主力合约自身历史，不是连续主力复权序列；换月附近需谨慎解释长周期指标。",
        "fetchedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }, rows


def main() -> None:
    report_date = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
    requested = tuple(
        symbol.strip().upper()
        for symbol in os.environ.get("TECHNICAL_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",")
        if symbol.strip()
    )
    contracts = {str(item["symbol"]): item for item in fetch_main_contracts()}
    output_dir = ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots: list[dict[str, object]] = []

    for symbol in requested:
        contract = contracts.get(symbol)
        if not contract:
            snapshots.append({"symbol": symbol, "reportDate": report_date, "status": "MAIN_CONTRACT_NOT_FOUND"})
            continue
        snapshot, rows = build_snapshot(contract, report_date)
        snapshots.append(snapshot)
        history_path = output_dir / f"eastmoney_technical_history_{symbol}_{report_date}.csv"
        with history_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["date"])
            writer.writeheader()
            writer.writerows(rows)

    snapshot_path = output_dir / f"eastmoney_technical_snapshot_{report_date}.json"
    snapshot_path.write_text(json.dumps({"reportDate": report_date, "items": snapshots}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Technical snapshot: {snapshot_path}")
    print(f"Requested symbols: {len(requested)}; OK: {sum(item.get('status') == 'OK' for item in snapshots)}")


if __name__ == "__main__":
    main()
