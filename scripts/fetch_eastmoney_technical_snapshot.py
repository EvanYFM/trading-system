"""Build daily moving-average and intraday Chan-structure snapshots."""

from __future__ import annotations

import csv
import json
import os
import re
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from fetch_eastmoney_main_quotes import (
    KLINE_FIELDS_1,
    KLINE_FIELDS_2,
    KLINE_URL,
    SOURCE_PAGE,
    fetch_main_contracts,
    get_json,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOLS = ("AG", "JM", "FU", "LH", "LC", "JD")
SINA_MINUTE_URL = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
    "{contract}_{period}_=/InnerFuturesNewService.getFewMinLine?symbol={contract}&type={period}"
)
SINA_DAILY_URL = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
    "{contract}=/InnerFuturesNewService.getDailyKLine?symbol={contract}"
)


def value(text: object) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def mean(values: list[float], period: int) -> float | None:
    return statistics.fmean(values[-period:]) if len(values) >= period else None


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


def parse_minute_payload(text: str, report_date: str) -> list[dict[str, object]]:
    match = re.search(r"=\((\[.*\])\);?\s*$", text, re.S)
    if not match:
        raise ValueError("Sina minute response is not valid JSONP")
    cutoff = datetime.strptime(report_date, "%Y%m%d").replace(hour=20)
    bars: list[dict[str, object]] = []
    for row in json.loads(match.group(1)):
        timestamp = datetime.strptime(row["d"], "%Y-%m-%d %H:%M:%S")
        if timestamp >= cutoff:
            continue
        bars.append(
            {
                "timestamp": timestamp,
                "open": value(row.get("o")),
                "high": value(row.get("h")),
                "low": value(row.get("l")),
                "close": value(row.get("c")),
                "volume": value(row.get("v")),
                "openInterest": value(row.get("p")),
            }
        )
    return bars


def fetch_minute_bars(contract: str, period: int, report_date: str) -> tuple[list[dict[str, object]], str]:
    symbol = contract.upper()
    url = SINA_MINUTE_URL.format(contract=symbol, period=period)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    return parse_minute_payload(text, report_date), url


def parse_sina_daily_payload(text: str, report_date: str) -> list[dict[str, float | str]]:
    match = re.search(r"=\((\[.*\])\);?\s*$", text, re.S)
    if not match:
        raise ValueError("Sina daily response is not valid JSONP")
    rows: list[dict[str, float | str]] = []
    previous_close: float | None = None
    for item in json.loads(match.group(1)):
        date = str(item.get("d", ""))
        if not date or date.replace("-", "") > report_date:
            continue
        close = value(item.get("c"))
        change_amount = close - previous_close if previous_close is not None else 0.0
        change_pct = change_amount / previous_close * 100 if previous_close else 0.0
        rows.append(
            {
                "date": date,
                "open": value(item.get("o")),
                "close": close,
                "high": value(item.get("h")),
                "low": value(item.get("l")),
                "volume": value(item.get("v")),
                "turnover": 0.0,
                "amplitude_pct": 0.0,
                "change_pct": change_pct,
                "change_amount": change_amount,
            }
        )
        previous_close = close
    return rows


def fetch_sina_daily_history(contract: str, report_date: str) -> list[dict[str, float | str]]:
    symbol = contract.upper()
    url = SINA_DAILY_URL.format(contract=symbol)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    return parse_sina_daily_payload(text, report_date)


def remove_inclusion(bars: list[dict[str, object]]) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []
    for bar in bars:
        current = dict(bar)
        if not cleaned:
            cleaned.append(current)
            continue
        previous = cleaned[-1]
        included = (
            (float(current["high"]) <= float(previous["high"]) and float(current["low"]) >= float(previous["low"]))
            or (float(current["high"]) >= float(previous["high"]) and float(current["low"]) <= float(previous["low"]))
        )
        if not included:
            cleaned.append(current)
            continue
        direction = 1
        if len(cleaned) >= 2:
            direction = 1 if float(previous["high"]) >= float(cleaned[-2]["high"]) else -1
        if direction > 0:
            previous["high"] = max(float(previous["high"]), float(current["high"]))
            previous["low"] = max(float(previous["low"]), float(current["low"]))
        else:
            previous["high"] = min(float(previous["high"]), float(current["high"]))
            previous["low"] = min(float(previous["low"]), float(current["low"]))
        previous["close"] = current["close"]
        previous["timestamp"] = current["timestamp"]
    return cleaned


def find_fractals(bars: list[dict[str, object]]) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    for index in range(1, len(bars) - 1):
        left, middle, right = bars[index - 1], bars[index], bars[index + 1]
        if (
            float(middle["high"]) > float(left["high"])
            and float(middle["high"]) > float(right["high"])
            and float(middle["low"]) > float(left["low"])
            and float(middle["low"]) > float(right["low"])
        ):
            points.append({"index": index, "kind": "top", "price": middle["high"], "timestamp": middle["timestamp"]})
        elif (
            float(middle["high"]) < float(left["high"])
            and float(middle["high"]) < float(right["high"])
            and float(middle["low"]) < float(left["low"])
            and float(middle["low"]) < float(right["low"])
        ):
            points.append({"index": index, "kind": "bottom", "price": middle["low"], "timestamp": middle["timestamp"]})
    return points


def build_strokes(points: list[dict[str, object]], minimum_gap: int = 4) -> list[dict[str, object]]:
    strokes: list[dict[str, object]] = []
    for point in points:
        if not strokes:
            strokes.append(point)
            continue
        previous = strokes[-1]
        if point["kind"] == previous["kind"]:
            more_extreme = (
                float(point["price"]) > float(previous["price"])
                if point["kind"] == "top"
                else float(point["price"]) < float(previous["price"])
            )
            if more_extreme:
                strokes[-1] = point
            continue
        if int(point["index"]) - int(previous["index"]) >= minimum_gap:
            strokes.append(point)
    return strokes


def classify_chan(strokes: list[dict[str, object]]) -> str:
    tops = [point for point in strokes if point["kind"] == "top"]
    bottoms = [point for point in strokes if point["kind"] == "bottom"]
    if len(tops) < 2 or len(bottoms) < 2:
        return "无法确认"
    if float(tops[-1]["price"]) > float(tops[-2]["price"]) and float(bottoms[-1]["price"]) > float(bottoms[-2]["price"]):
        return "偏多"
    if float(tops[-1]["price"]) < float(tops[-2]["price"]) and float(bottoms[-1]["price"]) < float(bottoms[-2]["price"]):
        return "偏空"
    return "中枢震荡"


def recent_central_zone(strokes: list[dict[str, object]]) -> dict[str, float] | None:
    if len(strokes) < 4:
        return None
    segments = [
        (min(float(left["price"]), float(right["price"])), max(float(left["price"]), float(right["price"])))
        for left, right in zip(strokes[-4:-1], strokes[-3:])
    ]
    lower = max(segment[0] for segment in segments)
    upper = min(segment[1] for segment in segments)
    return {"lower": lower, "upper": upper} if lower <= upper else None


def serialize_points(points: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "timestamp": point["timestamp"].isoformat(sep=" ", timespec="minutes"),
            "price": point["price"],
        }
        for point in points[-2:]
    ]


def session_activity(bars: list[dict[str, object]], report_date: str) -> dict[str, float | None]:
    report_day = datetime.strptime(report_date, "%Y%m%d").date()
    end_index = next(
        (index for index in range(len(bars) - 1, -1, -1) if bars[index]["timestamp"].date() == report_day and bars[index]["timestamp"].hour < 20),
        None,
    )
    if end_index is None:
        return {"volume": None, "previousVolume": None, "openInterest": None, "openInterestChange": None}

    def session_start(end: int) -> int:
        for index in range(end, -1, -1):
            timestamp = bars[index]["timestamp"]
            if timestamp.hour < 20:
                continue
            if index == 0:
                return index
            previous = bars[index - 1]["timestamp"]
            if previous.hour < 20 or (timestamp - previous).total_seconds() > 4 * 3600:
                return index
        day = bars[end]["timestamp"].date()
        return next((index for index in range(end + 1) if bars[index]["timestamp"].date() == day), 0)

    current_start = session_start(end_index)
    current = bars[current_start : end_index + 1]
    previous_end = current_start - 1
    previous_start = session_start(previous_end) if previous_end >= 0 else 0
    previous = bars[previous_start : previous_end + 1] if previous_end >= 0 else []
    current_volume = sum(float(bar["volume"]) for bar in current)
    previous_volume = sum(float(bar["volume"]) for bar in previous) if previous else None
    current_position = float(current[-1]["openInterest"])
    previous_position = float(previous[-1]["openInterest"]) if previous else None
    return {
        "volume": current_volume,
        "previousVolume": previous_volume,
        "openInterest": current_position,
        "openInterestChange": current_position - previous_position if previous_position is not None else None,
    }


def build_chan_snapshot(contract: str, period: int, report_date: str) -> dict[str, object]:
    try:
        bars, source_url = fetch_minute_bars(contract, period, report_date)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return {"period": period, "status": "FETCH_FAILED", "state": "无法确认", "error": type(error).__name__}
    lookback = 160 if period == 15 else 120
    sample = bars[-lookback:]
    if len(sample) < 20:
        return {"period": period, "status": "INSUFFICIENT_BARS", "state": "无法确认", "barCount": len(sample), "sourceUrl": source_url}
    cleaned = remove_inclusion(sample)
    strokes = build_strokes(find_fractals(cleaned))
    tops = [point for point in strokes if point["kind"] == "top"]
    bottoms = [point for point in strokes if point["kind"] == "bottom"]
    state = classify_chan(strokes)
    activity = session_activity(bars, report_date)
    return {
        "period": period,
        "status": "OK" if state != "无法确认" else "INSUFFICIENT_STRUCTURE",
        "state": state,
        "barCount": len(sample),
        "processedBarCount": len(cleaned),
        "strokeCount": len(strokes),
        "startTime": sample[0]["timestamp"].isoformat(sep=" ", timespec="minutes"),
        "endTime": sample[-1]["timestamp"].isoformat(sep=" ", timespec="minutes"),
        "latestClose": sample[-1]["close"],
        "recentTops": serialize_points(tops),
        "recentBottoms": serialize_points(bottoms),
        "centralZone": recent_central_zone(strokes),
        "activity": activity,
        "source": "新浪财经主力合约分钟K线",
        "sourceUrl": source_url,
    }


def classify_daily_ma(close: float, ma5: float | None, ma20: float | None, ma60: float | None) -> str:
    if None in (ma5, ma20, ma60):
        return "无法确认"
    if close > float(ma5) > float(ma20) > float(ma60):
        return "偏多"
    if close < float(ma5) < float(ma20) < float(ma60):
        return "偏空"
    return "中枢震荡"


def classify_position_price(change_pct: float, open_interest_change: float | None) -> dict[str, str]:
    if open_interest_change is None:
        return {"label": "持仓数据不足", "impulse": "无法确认"}
    position = "增仓" if open_interest_change > 0 else "减仓" if open_interest_change < 0 else "持仓平"
    price = "上涨" if change_pct > 0 else "下跌" if change_pct < 0 else "价格平"
    if position == "增仓" and price == "上涨":
        impulse = "多头推动"
    elif position == "增仓" and price == "下跌":
        impulse = "空头推动"
    elif position == "减仓" and price == "上涨":
        impulse = "空头回补"
    elif position == "减仓" and price == "下跌":
        impulse = "多头撤退"
    else:
        impulse = "方向有限"
    return {"label": f"{position}{price}", "impulse": impulse}


def build_key_levels(close: float, ma_values: dict[str, float | None], chan_snapshots: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    candidates: list[dict[str, object]] = [
        {"label": label, "value": level, "source": "均线"}
        for label, level in ma_values.items()
        if level is not None
    ]
    for snapshot in chan_snapshots:
        zone = snapshot.get("centralZone")
        if not isinstance(zone, dict):
            continue
        period = snapshot.get("period")
        candidates.extend(
            [
                {"label": f"{period}分钟中枢下沿", "value": zone["lower"], "source": "中枢"},
                {"label": f"{period}分钟中枢上沿", "value": zone["upper"], "source": "中枢"},
            ]
        )
    supports = sorted((item for item in candidates if float(item["value"]) <= close), key=lambda item: close - float(item["value"]))
    resistances = sorted((item for item in candidates if float(item["value"]) > close), key=lambda item: float(item["value"]) - close)
    return {"supports": supports[:2], "resistances": resistances[:2]}


def combine_technical_bias(
    daily_state: str,
    chan15_state: str,
    chan60_state: str,
    impulse: str,
    volume_ratio: float | None,
) -> dict[str, object]:
    direction = {"偏多": 1.0, "偏空": -1.0, "中枢震荡": 0.0, "无法确认": 0.0}
    score = direction.get(daily_state, 0.0) + direction.get(chan15_state, 0.0) + direction.get(chan60_state, 0.0) * 2
    impulse_score = {"多头推动": 1.5, "空头推动": -1.5, "空头回补": 0.5, "多头撤退": -0.5}.get(impulse, 0.0)
    if volume_ratio is not None:
        impulse_score *= 1.25 if volume_ratio >= 1.2 else 0.75 if volume_ratio <= 0.8 else 1.0
    score += impulse_score
    bias = "偏多" if score >= 2 else "偏空" if score <= -2 else "中枢震荡"
    strength = "强" if abs(score) >= 4.5 else "中" if abs(score) >= 2 else "弱"
    return {"bias": bias, "score": score, "strength": strength}


def read_cached_history(symbol: str, report_date: str) -> list[dict[str, float | str]]:
    path = ROOT / "data" / f"eastmoney_technical_history_{symbol}_{report_date}.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key: value(raw) if key != "date" else raw for key, raw in row.items()}
            for row in csv.DictReader(handle)
        ]


def read_report_contracts(report_date: str) -> dict[str, dict[str, object]]:
    path = ROOT / "data" / f"eastmoney_main_quotes_{report_date}.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            row["symbol"].upper(): {
                "symbol": row["symbol"].upper(),
                "variety": row.get("variety", ""),
                "contract": row.get("contract", ""),
                "market": int(value(row.get("market"))),
            }
            for row in csv.DictReader(handle)
            if row.get("symbol") and row.get("contract") and row.get("status") == "OK"
        }


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
        params = {
            "secid": secid,
            "klt": 101,
            "fqt": 1,
            "beg": begin_date,
            "end": report_date,
            "iscca": 1,
            "fields1": KLINE_FIELDS_1,
            "fields2": KLINE_FIELDS_2,
        }
        try:
            payload = get_json(KLINE_URL, params)
        except OSError:
            time.sleep(1)
            payload = get_json(KLINE_URL, params)
        rows = parse_klines(((payload.get("data") or {}).get("klines") or []))
    except OSError:
        rows = read_cached_history(str(contract["symbol"]), report_date)
        if rows:
            history_status = "CACHED_HISTORY"
        else:
            rows = fetch_sina_daily_history(str(contract["contract"]), report_date)
            history_status = "SINA_DAILY_FALLBACK"
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
    ma5 = mean(closes, 5)
    ma20 = mean(closes, 20)
    ma60 = mean(closes, 60)
    daily_state = classify_daily_ma(closes[-1], ma5, ma20, ma60)
    chan15 = build_chan_snapshot(str(contract["contract"]), 15, report_date)
    chan60 = build_chan_snapshot(str(contract["contract"]), 60, report_date)
    activity = chan15.get("activity", {}) if isinstance(chan15.get("activity"), dict) else {}
    volume_now = float(rows[-1]["volume"])
    volume_previous = float(rows[-2]["volume"]) if len(rows) >= 2 else None
    volume_ratio = volume_now / volume_previous if volume_previous else None
    position_price = classify_position_price(float(rows[-1]["change_pct"]), activity.get("openInterestChange"))
    combined = combine_technical_bias(daily_state, str(chan15["state"]), str(chan60["state"]), position_price["impulse"], volume_ratio)
    key_levels = build_key_levels(
        closes[-1],
        {"MA5": ma5, "MA20": ma20, "MA60": ma60},
        [chan15, chan60],
    )

    latest = rows[-1]
    daily_source = "新浪财经合约日线 + 东方财富报告日收盘校正" if history_status.startswith("SINA") else "东方财富期货主力合约日线"
    return {
        **contract,
        "reportDate": report_date,
        "sourceDate": str(latest["date"]),
        "status": "OK" if str(latest["date"]).replace("-", "") == report_date else "STALE",
        "source": daily_source,
        "sourceUrl": SOURCE_PAGE,
        "historyStatus": history_status,
        "barCount": len(rows),
        "startDate": rows[0]["date"],
        "endDate": rows[-1]["date"],
        "close": closes[-1],
        "changePct": float(latest["change_pct"]),
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "dailyState": daily_state,
        "chan15": chan15,
        "chan60": chan60,
        "marketActivity": {
            "volume": volume_now,
            "previousVolume": volume_previous,
            "volumeRatio": volume_ratio,
            "openInterest": activity.get("openInterest"),
            "openInterestChange": activity.get("openInterestChange"),
            **position_price,
        },
        "keyLevels": key_levels,
        "bias": combined["bias"],
        "score": combined["score"],
        "signalStrength": combined["strength"],
        "method": "日线 MA5/20/60、成交量与持仓量、15/60 分钟简化缠论结构三层验证",
        "limitations": "日线为当前主力合约自身历史，不是复权连续合约；分钟结构先处理包含关系，再以三根K线分型和最少4根处理后K线构成简化笔，不等同于严格缠论背驰或一、二、三类买卖点。",
        "fetchedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }, rows


def main() -> None:
    report_date = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
    requested = tuple(
        symbol.strip().upper()
        for symbol in os.environ.get("TECHNICAL_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",")
        if symbol.strip()
    )
    report_contracts = read_report_contracts(report_date)
    try:
        contracts = {str(item["symbol"]): item for item in fetch_main_contracts()}
    except (OSError, TimeoutError):
        contracts = {}
    contracts.update(report_contracts)
    output_dir = ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots: list[dict[str, object]] = []

    for symbol in requested:
        contract = contracts.get(symbol)
        if not contract:
            snapshots.append({"symbol": symbol, "reportDate": report_date, "status": "MAIN_CONTRACT_NOT_FOUND"})
            continue
        try:
            snapshot, rows = build_snapshot(contract, report_date)
        except (OSError, ValueError) as error:
            snapshot = {
                **contract,
                "reportDate": report_date,
                "status": "DAILY_FETCH_FAILED",
                "error": type(error).__name__,
            }
            rows = []
        snapshots.append(snapshot)
        if rows:
            history_path = output_dir / f"eastmoney_technical_history_{symbol}_{report_date}.csv"
            with history_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        time.sleep(0.4)

    snapshot_path = output_dir / f"eastmoney_technical_snapshot_{report_date}.json"
    snapshot_path.write_text(json.dumps({"reportDate": report_date, "items": snapshots}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Technical snapshot: {snapshot_path}")
    print(f"Requested symbols: {len(requested)}; OK: {sum(item.get('status') == 'OK' for item in snapshots)}")


if __name__ == "__main__":
    main()
