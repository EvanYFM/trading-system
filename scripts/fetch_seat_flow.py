# -*- coding: utf-8 -*-
"""抓取席位大资金动向所需的原始持仓变化数据。

每日流程在 build_research_dashboard.py 之前运行：
    REPORT_DATE=YYYYMMDD python scripts/fetch_seat_flow.py

输出 data/seat_flow_rows_YYYYMMDD.json：
    {"date": "2026-09-10", "fetchedAt": ..., "brokers": {"高盛期货": [{variety, contract, net, long_chg, short_chg}], ...}}

席位分组（与总览页「席位大资金动向」板块一致，剔除股指/国债在计算层做）：
    外资：高盛期货、瑞银期货、摩根大通
    内资：国泰君安、东证期货、永安期货、中财期货、东吴期货
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))

FOREIGN_BROKERS = ["高盛期货", "瑞银期货", "摩根大通"]
DOMESTIC_BROKERS = ["国泰君安", "东证期货", "永安期货", "中财期货", "东吴期货"]


def load_base_module():
    spec = importlib.util.spec_from_file_location("futures_report_base", ROOT / "scripts" / "generate_futures_report.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 scripts/generate_futures_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contract_symbol(contract: str) -> str:
    """从合约代码提取品种代码前缀：pk2610 -> PK，IF2509 -> IF。"""
    return "".join(ch for ch in (contract or "") if ch.isalpha()).upper()


def main():
    base = load_base_module()
    requested = f"{RUN_DATE[:4]}-{RUN_DATE[4:6]}-{RUN_DATE[6:8]}"
    brokers_out = {}
    failures = []
    for broker in FOREIGN_BROKERS + DOMESTIC_BROKERS:
        try:
            date, _url, rows = base.fetch_broker(broker, requested)
            if not rows:
                failures.append(f"{broker}: 无数据")
                continue
            if date and date != requested:
                failures.append(f"{broker}: 返回日期 {date} != {requested}")
                continue
            brokers_out[broker] = [
                {"variety": r.get("variety"), "contract": r.get("contract"), "symbol": contract_symbol(r.get("contract") or ""),
                 "net": r.get("net"), "long_chg": r.get("long_chg"), "short_chg": r.get("short_chg")}
                for r in rows
            ]
            print(f"{broker}: {date} {len(rows)} 行 ✓")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{broker}: {exc}")
            print(f"{broker}: 抓取失败 {exc}")

    payload = {
        "date": requested,
        "fetchedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "brokers": brokers_out,
    }
    if failures:
        payload["failures"] = failures
    out_path = ROOT / "data" / f"seat_flow_rows_{RUN_DATE}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"out={out_path} | 席位 {len(brokers_out)}/8 | 失败 {len(failures)}")
    if len(brokers_out) < 8:
        print("警告：席位不完整，缺失的席位在快照中标记，不伪造数据")


if __name__ == "__main__":
    main()
