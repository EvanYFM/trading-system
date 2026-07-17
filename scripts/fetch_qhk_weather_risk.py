"""Fetch public agricultural weather alerts from QHKCH AI Eye."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://eye.qhkch.com/?view=overview"
DASHBOARD_URL = "https://eye.qhkch.com/api/weather/dashboard"
FORECAST_URL = "https://eye.qhkch.com/api/weather/forecast-warnings?limit=200"

AGRI_SECTORS = {
    "M": "谷物饲料",
    "RM": "谷物饲料",
    "C": "谷物饲料",
    "A": "谷物饲料",
    "B": "谷物饲料",
    "P": "油脂油料",
    "OI": "油脂油料",
    "PK": "油脂油料",
    "Y": "油脂油料",
    "CF": "农副软商",
    "SR": "农副软商",
    "LH": "农副软商",
    "AP": "农副软商",
    "JD": "农副软商",
    "CJ": "农副软商",
}

RISK_TYPE_NAMES = {
    "high_temp": "高温",
    "low_temp": "低温",
    "rain": "强降雨",
    "continuous_rain": "连续降雨",
    "drought": "持续少雨/干旱",
    "wind": "大风",
}


def get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def risk_text(risk_types: dict | None) -> str:
    if not risk_types:
        return "-"
    active = [RISK_TYPE_NAMES.get(key, key) for key, value in risk_types.items() if value in {"high", "medium"}]
    return "、".join(active) or "-"


def fetch_weather_risk() -> tuple[pd.DataFrame, dict]:
    dashboard = get_json(DASHBOARD_URL)
    forecast = get_json(FORECAST_URL)
    stats = dashboard.get("stats", {})
    data_date = str(stats.get("data_date", ""))

    events_by_symbol: dict[str, list[dict]] = {}
    for item in dashboard.get("high_risk_events", []):
        symbol = str(item.get("symbol", "")).upper()
        if symbol in AGRI_SECTORS:
            events_by_symbol.setdefault(symbol, []).append(item)

    reactions = {
        str(item.get("symbol", "")).upper(): item
        for item in dashboard.get("market_reactions", {}).get("items", [])
    }

    rows: list[dict] = []
    for item in dashboard.get("matrix", []):
        symbol = str(item.get("symbol", "")).upper()
        if symbol not in AGRI_SECTORS or item.get("overall") not in {"high", "medium"}:
            continue
        events = events_by_symbol.get(symbol, [])
        origins = []
        reasons = []
        for event in events:
            origin = event.get("origin", {})
            if origin.get("origin_name"):
                origins.append(str(origin["origin_name"]))
            if event.get("trigger_reason"):
                reasons.append(str(event["trigger_reason"]))
        reaction = reactions.get(symbol, {})
        reflection = reaction.get("market_reflection", {})
        rows.append(
            {
                "data_date": data_date,
                "alert_window": "今日",
                "alert_date": data_date,
                "sector": AGRI_SECTORS[symbol],
                "symbol": symbol,
                "variety": item.get("commodity_name", ""),
                "risk_level": item.get("overall", ""),
                "risk_score": item.get("score", 0),
                "risk_types": risk_text({key: item.get(key) for key in RISK_TYPE_NAMES}),
                "origins": "、".join(dict.fromkeys(origins)) or "-",
                "trigger_reason": "；".join(dict.fromkeys(reasons[:2])) or "查看风险类型与产地明细",
                "market_reflection": reflection.get("label", reaction.get("reaction_label", "待验证")),
                "market_summary": reflection.get("summary", reaction.get("market_verdict", "")),
                "source_url": SOURCE_URL,
            }
        )

    for item in forecast.get("items", []):
        symbol = str(item.get("symbol", "")).upper()
        if symbol not in AGRI_SECTORS:
            continue
        rows.append(
            {
                "data_date": str(forecast.get("anchor_date", data_date)),
                "alert_window": "未来",
                "alert_date": item.get("warning_date", ""),
                "sector": AGRI_SECTORS[symbol],
                "symbol": symbol,
                "variety": item.get("commodity_name", ""),
                "risk_level": item.get("risk_level", ""),
                "risk_score": item.get("forecast_score", 0),
                "risk_types": risk_text(item.get("risk_types")),
                "origins": item.get("origin_name", "-"),
                "trigger_reason": item.get("trigger_reason", item.get("summary", "")),
                "market_reflection": item.get("pricing_label", "待验证"),
                "market_summary": "未来预警仅描述天气风险，不预测价格方向。",
                "source_url": SOURCE_URL,
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["risk_score"] = pd.to_numeric(frame["risk_score"], errors="coerce").fillna(0)
        frame = frame.sort_values(["sector", "alert_window", "risk_score"], ascending=[True, True, False])

    status = {
        "source": "奇货可查 AI天眼",
        "source_url": SOURCE_URL,
        "data_date": data_date,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_alerts": int((frame["alert_window"] == "今日").sum()) if not frame.empty else 0,
        "future_alerts": int((frame["alert_window"] == "未来").sum()) if not frame.empty else 0,
        "monitored_symbols": stats.get("symbol_count", 0),
        "high_risk_symbols": stats.get("high_risk_symbols", 0),
    }
    return frame, status


def main() -> None:
    run_date = datetime.now().strftime("%Y%m%d")
    frame, status = fetch_weather_risk()
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / f"qhk_weather_risk_{run_date}.csv"
    status_path = data_dir / f"qhk_weather_risk_status_{run_date}.json"
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"weather risk: {csv_path}")
    print(f"alerts: {len(frame)}")


if __name__ == "__main__":
    main()
