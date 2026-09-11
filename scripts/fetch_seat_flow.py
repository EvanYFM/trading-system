# -*- coding: utf-8 -*-
"""抓取席位大资金动向所需的「净实值变化」金额数据（口径 2026-09-11 用户确认）。

数据源：奇货可查席位持仓结构页
    https://x.qhkch.com/broker/structure?broker=<席位>&sortBy=chge_value&sortDirection=desc
该页「净实值变化」列即当日席位各品种的净流动金额（流多 X.XX亿 / 流空 X.XX亿）。

每日流程在 build_research_dashboard.py 之前运行：
    REPORT_DATE=YYYYMMDD python scripts/fetch_seat_flow.py

输出 data/seat_flow_amount_YYYYMMDD.json：
    {"date": ..., "fetchedAt": ..., "brokers": {"高盛期货": [{"variety": "沪金", "netValueChange": 1047000000.0}, ...]}}

席位分组（剔除股指/国债在 build 层做）：
    外资：高盛期货、瑞银期货、摩根大通
    内资：国泰君安、东证期货、永安期货、中财期货、东吴期货
"""
from __future__ import annotations

import html
import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))

FOREIGN_BROKERS = ["高盛期货", "瑞银期货", "摩根大通"]
DOMESTIC_BROKERS = ["国泰君安", "东证期货", "永安期货", "中财期货", "东吴期货"]

# structure 页品种名 → 品种代码（用于剔除金融与前端跳转；匹配不上则 symbol 为空，仍参与排序）
STRUCTURE_SYMBOL_MAP = {
    "沪金": "AU", "沪银": "AG", "沪铜": "CU", "沪铝": "AL", "沪锌": "ZN",
    "沪镍": "NI", "沪锡": "SN", "沪铅": "PB", "国际铜": "BC", "氧化铝": "AO",
    "铁矿石": "I", "螺纹钢": "RB", "热卷": "HC", "不锈钢": "SS", "线材": "WR",
    "焦煤": "JM", "焦炭": "J", "硅铁": "SF", "锰硅": "SM", "工业硅": "SI",
    "碳酸锂": "LC", "多晶硅": "PS",
    "原油": "SC", "燃油": "FU", "低硫燃油": "LU", "沥青": "BU", "LPG": "PG",
    "PTA": "TA", "甲醇": "MA", "PVC": "V", "PP": "PP", "塑料": "L",
    "乙二醇": "EG", "苯乙烯": "EB", "纯碱": "SA", "玻璃": "FG", "尿素": "UR",
    "短纤": "PF", "瓶片": "PR", "橡胶": "RU", "20号胶": "NR", "合成橡胶": "BR",
    "纸浆": "SP", "对二甲苯": "PX", "纯苯": "BZ", "烧碱": "SH", "丙烷": "PL",
    "集运欧线": "EC", "欧线集运": "EC",
    "豆粕": "M", "豆油": "Y", "豆一": "A", "豆二": "B", "棕榈油": "P",
    "菜油": "OI", "菜粕": "RM", "白糖": "SR", "棉花": "CF", "玉米": "C",
    "淀粉": "CS", "鸡蛋": "JD", "生猪": "LH", "苹果": "AP", "红枣": "CJ",
    "花生": "PK", "棉纱": "CY", "原木": "LG", "胶合板": "BB", "纤维板": "FB",
    "玉米淀粉": "CS",
}


def load_base_module():
    spec = importlib.util.spec_from_file_location("futures_report_base", ROOT / "scripts" / "generate_futures_report.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 scripts/generate_futures_report.py")
    module = importlib.util.module_from_spec(spec)
    # structure 页面需要 qhkch VIP 登录态：环境变量优先，其次 config/qhkch_cookie.txt（gitignore）
    if not os.environ.get("QHKCH_COOKIE"):
        cookie_file = ROOT / "config" / "qhkch_cookie.txt"
        if cookie_file.is_file():
            os.environ["QHKCH_COOKIE"] = cookie_file.read_text(encoding="utf-8").strip()
    spec.loader.exec_module(module)
    return module


def parse_change_amount(text: str) -> float | None:
    """'流多 10.47亿' → +1.047e9；'流空 0.73亿' → -7.3e7；无法解析返回 None"""
    text = html.unescape(text or "").strip()
    match = re.search(r"流(多|空)\s*([\d.]+)\s*(亿|万)", text)
    if not match:
        return None
    value = float(match.group(2))
    if match.group(3) == "亿":
        value *= 1e8
    else:
        value *= 1e4
    return value if match.group(1) == "多" else -value


def fetch_structure_amounts(base, broker: str, requested: str) -> list[dict]:
    url = "https://x.qhkch.com/broker/structure?broker=" + quote(broker) + "&sortBy=chge_value&sortDirection=desc"
    if requested:
        url += "&date=" + quote(requested)
    text = base.fetch_url(url)
    title = re.search(r"持仓结构\s*(\d{4}-\d{2}-\d{2})", text)
    page_date = title.group(1) if title else None
    if page_date and page_date != requested:
        raise RuntimeError(f"页面日期 {page_date} != {requested}")
    rows = []
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_match.group(1), re.S)
        clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if len(clean) < 3 or clean[0] in ("商品",) or clean[0].startswith("国泰君安 所有") is False and "持仓结构" in " ".join(clean):
            continue
        variety = clean[0]
        if not variety or "持仓结构" in variety:
            continue
        amount = parse_change_amount(clean[2] if len(clean) > 2 else "")
        if amount is None:
            continue
        rows.append({"variety": variety, "symbol": STRUCTURE_SYMBOL_MAP.get(variety, ""), "netValueChange": amount})
    if not rows:
        raise RuntimeError("structure 页面未解析到数据行")
    return rows


def main():
    base = load_base_module()
    requested = f"{RUN_DATE[:4]}-{RUN_DATE[4:6]}-{RUN_DATE[6:8]}"
    brokers_out = {}
    failures = []
    for broker in FOREIGN_BROKERS + DOMESTIC_BROKERS:
        try:
            rows = fetch_structure_amounts(base, broker, requested)
            brokers_out[broker] = rows
            top = sorted(rows, key=lambda r: r["netValueChange"], reverse=True)[:2]
            print(f"{broker}: {len(rows)} 品种 ✓ 最高 {top[0]['variety']} {top[0]['netValueChange']/1e8:+.2f}亿")
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
    out_path = ROOT / "data" / f"seat_flow_amount_{RUN_DATE}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"out={out_path} | 席位 {len(brokers_out)}/8 | 失败 {len(failures)}")


if __name__ == "__main__":
    main()
