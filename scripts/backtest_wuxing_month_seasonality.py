from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE_TEMPLATE = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
    "{symbol}0=/InnerFuturesNewService.getDailyKLine?symbol={symbol}0"
)
MONTH_CALENDAR = {
    1: ("丑", "土"),
    2: ("寅", "木"),
    3: ("卯", "木"),
    4: ("辰", "土"),
    5: ("巳", "火"),
    6: ("午", "火"),
    7: ("未", "土"),
    8: ("申", "金"),
    9: ("酉", "金"),
    10: ("戌", "土"),
    11: ("亥", "水"),
    12: ("子", "水"),
}
SYMBOL_ATTRIBUTES = {
    "AU": ("沪金", "金", "贵金属"),
    "AG": ("沪银", "金", "贵金属"),
    "CU": ("沪铜", "金", "有色金属"),
    "AL": ("沪铝", "金", "有色金属"),
    "ZN": ("沪锌", "金", "有色金属"),
    "PB": ("沪铅", "金", "有色金属"),
    "NI": ("沪镍", "金", "有色金属"),
    "SN": ("沪锡", "金", "有色金属"),
    "LC": ("碳酸锂", "金", "有色金属"),
    "SC": ("原油", "火", "油化工"),
    "FU": ("燃料油", "火", "油化工"),
    "LU": ("低硫燃料油", "火", "油化工"),
    "PG": ("LPG", "火", "油化工"),
    "JM": ("焦煤", "火", "黑色系"),
    "J": ("焦炭", "火", "黑色系"),
    "RU": ("天然橡胶", "木", "油化工"),
    "NR": ("20号胶", "木", "农副软商"),
    "SP": ("纸浆", "木", "其他商品"),
    "I": ("铁矿石", "土", "黑色系"),
    "FG": ("玻璃", "土", "家人品种"),
    "SA": ("纯碱", "土", "家人品种"),
    "EC": ("集运欧线", "水", "其他商品"),
}
MIN_TOTAL_MONTHS = 60
MIN_RESONANCE_MONTHS = 15
MIN_ABS_CORRELATION = 0.15
MAX_FDR_Q = 0.10
FLAT_THRESHOLD = 0.01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest Five-Element month seasonality.")
    parser.add_argument("--report-date", required=True, help="Beijing report date in YYYYMMDD.")
    parser.add_argument("--permutations", type=int, default=5000)
    return parser.parse_args()


def fetch_daily(symbol: str) -> tuple[list[dict[str, object]], str]:
    url = SOURCE_TEMPLATE.format(symbol=symbol)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    match = re.search(r"=\((\[.*\])\);?\s*$", text, re.S)
    if not match:
        raise RuntimeError("daily response could not be parsed")
    rows = json.loads(match.group(1))
    return rows, url


def monthly_returns(rows: list[dict[str, object]], cutoff: str) -> list[dict[str, object]]:
    month_ends: dict[str, tuple[str, float]] = {}
    for row in rows:
        date = str(row.get("d", ""))[:10]
        if not date or date > cutoff:
            continue
        close = float(row.get("c", 0) or 0)
        if close <= 0:
            continue
        key = date[:7]
        if key not in month_ends or date > month_ends[key][0]:
            month_ends[key] = (date, close)
    ordered = sorted(month_ends.items())
    result = []
    for index in range(1, len(ordered)):
        key, (date, close) = ordered[index]
        previous_close = ordered[index - 1][1][1]
        if previous_close <= 0:
            continue
        result.append(
            {
                "month": key,
                "date": date,
                "calendarMonth": int(key[5:7]),
                "return": close / previous_close - 1,
            }
        )
    return result


def pearson_binary(indicator: list[int], values: list[float]) -> float:
    if len(indicator) != len(values) or len(values) < 3:
        return 0.0
    x_mean = mean(indicator)
    y_mean = mean(values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(indicator, values))
    x_ss = sum((x - x_mean) ** 2 for x in indicator)
    y_ss = sum((y - y_mean) ** 2 for y in values)
    return numerator / math.sqrt(x_ss * y_ss) if x_ss and y_ss else 0.0


def permutation_p_value(
    indicator: list[int],
    values: list[float],
    observed: float,
    permutations: int,
    seed: int,
) -> float:
    rng = random.Random(seed)
    shuffled = list(values)
    extreme = 0
    for _ in range(permutations):
        rng.shuffle(shuffled)
        if abs(pearson_binary(indicator, shuffled)) >= abs(observed):
            extreme += 1
    return (extreme + 1) / (permutations + 1)


def benjamini_hochberg(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(count, 0, -1):
        symbol, value = ordered[rank - 1]
        running = min(running, value * count / rank)
        adjusted[symbol] = min(1.0, running)
    return adjusted


def probability_summary(values: list[float]) -> dict[str, float | int]:
    total = len(values)
    up = sum(value > FLAT_THRESHOLD for value in values)
    down = sum(value < -FLAT_THRESHOLD for value in values)
    flat = total - up - down
    return {
        "sampleCount": total,
        "upProbability": up / total if total else 0.0,
        "downProbability": down / total if total else 0.0,
        "flatProbability": flat / total if total else 0.0,
        "averageReturn": mean(values) if values else 0.0,
        "medianReturn": median(values) if total else 0.0,
    }


def analyze_symbol(
    symbol: str,
    rows: list[dict[str, object]],
    cutoff: str,
    permutations: int,
) -> dict[str, object]:
    variety, element, sector = SYMBOL_ATTRIBUTES[symbol]
    observations = monthly_returns(rows, cutoff)
    indicator = [int(MONTH_CALENDAR[item["calendarMonth"]][1] == element) for item in observations]
    values = [float(item["return"]) for item in observations]
    correlation = pearson_binary(indicator, values)
    seed = int(hashlib.sha256(symbol.encode("ascii")).hexdigest()[:8], 16)
    p_value = permutation_p_value(indicator, values, correlation, permutations, seed)
    resonance_values = [value for value, marker in zip(values, indicator) if marker]
    other_values = [value for value, marker in zip(values, indicator) if not marker]
    return {
        "symbol": symbol,
        "variety": variety,
        "sector": sector,
        "attributeElement": element,
        "status": "OK",
        "dataStartDate": observations[0]["date"] if observations else "",
        "dataEndDate": observations[-1]["date"] if observations else "",
        "totalMonths": len(observations),
        "resonance": probability_summary(resonance_values),
        "nonResonance": probability_summary(other_values),
        "correlation": correlation,
        "pValue": p_value,
        "effect": (mean(resonance_values) if resonance_values else 0.0)
        - (mean(other_values) if other_values else 0.0),
    }


def main() -> None:
    args = parse_args()
    report_date = datetime.strptime(args.report_date, "%Y%m%d")
    cutoff = report_date.strftime("%Y-%m-%d")
    results: dict[str, dict[str, object]] = {}
    sources: dict[str, str] = {}
    for symbol in SYMBOL_ATTRIBUTES:
        try:
            rows, url = fetch_daily(symbol)
            results[symbol] = analyze_symbol(symbol, rows, cutoff, args.permutations)
            sources[symbol] = url
        except Exception as exc:
            variety, element, sector = SYMBOL_ATTRIBUTES[symbol]
            results[symbol] = {
                "symbol": symbol,
                "variety": variety,
                "sector": sector,
                "attributeElement": element,
                "status": "UNAVAILABLE",
                "note": str(exc),
            }

    valid = {symbol: float(item["pValue"]) for symbol, item in results.items() if item["status"] == "OK"}
    adjusted = benjamini_hochberg(valid)
    current_month = report_date.month
    branch, month_element = MONTH_CALENDAR[current_month]
    for symbol, item in results.items():
        if item["status"] != "OK":
            continue
        q_value = adjusted[symbol]
        qualified = (
            int(item["totalMonths"]) >= MIN_TOTAL_MONTHS
            and int(item["resonance"]["sampleCount"]) >= MIN_RESONANCE_MONTHS
            and abs(float(item["correlation"])) >= MIN_ABS_CORRELATION
            and q_value <= MAX_FDR_Q
        )
        item["fdrQValue"] = q_value
        item["qualified"] = qualified
        item["currentMonth"] = {
            "month": current_month,
            "branch": branch,
            "element": month_element,
            "resonates": month_element == item["attributeElement"],
        }
        item["judgement"] = (
            "历史正向共振"
            if qualified and float(item["effect"]) > FLAT_THRESHOLD
            else "历史负向共振"
            if qualified and float(item["effect"]) < -FLAT_THRESHOLD
            else "未形成统计共振"
        )

    output = {
        "reportDate": args.report_date,
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "source": "新浪财经期货主力连续日线",
        "sources": sources,
        "methodology": {
            "returnDefinition": "月末收盘价相对上月末收盘价的收益率",
            "resonanceDefinition": "品种属性五行与公历月对应地支五行相同",
            "flatThreshold": FLAT_THRESHOLD,
            "permutations": args.permutations,
            "multipleTesting": "Benjamini-Hochberg FDR",
            "qualification": {
                "minimumTotalMonths": MIN_TOTAL_MONTHS,
                "minimumResonanceMonths": MIN_RESONANCE_MONTHS,
                "minimumAbsoluteCorrelation": MIN_ABS_CORRELATION,
                "maximumFdrQValue": MAX_FDR_Q,
            },
            "limitations": "五行分类是待检验标签，不构成因果机制；主力连续换月、交易制度和宏观结构变化会影响结果。",
        },
        "monthCalendar": [
            {"month": month, "branch": values[0], "element": values[1]}
            for month, values in MONTH_CALENDAR.items()
        ],
        "instruments": results,
    }
    output_path = ROOT / "data" / f"wuxing_month_seasonality_{args.report_date}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    qualified_count = sum(bool(item.get("qualified")) for item in results.values())
    print(f"Wrote {output_path} ({qualified_count} qualified of {len(results)})")


if __name__ == "__main__":
    main()
