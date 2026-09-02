# -*- coding: utf-8 -*-
"""把语雀导出的「月度投资复盘.md」转成工作站可导入的结构化 JSON。

文件是 HTML 混合的语雀导出格式，先剥标签再解析。

解析目标：
1. 月度盈亏汇总（"3月（亏损15W）" -> -150000）
2. 6/7/8 月的结构化复盘表格（执行质量归因）
3. 从表格描述里还原多笔操作序列，如 8 月 JM2701：
   1400开仓 -> 1450加仓 -> 1500加仓 -> 1500/1555止损
4. 3/4/5 月的叙述性记录（半结构化，只做宽松提取，其余保留原文）

口径：金额 "2W5" = 2万5 = 25000；"15W" = 150000。解析不出来的留空，不猜。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_trading_log_excel import (  # 复用同一套品种映射，保证口径一致
    VARIETY_CODE, CODE_VARIETY, find_varieties, parse_instrument,
)

SRC = r"C:\Users\29266\Desktop\月度投资复盘.md"
OUT = r"C:\Users\29266\WorkBuddy\已有网站优化\trading-system\data\imported\monthly_review_md.json"
YEAR = 2026  # 本文档为 2026 年复盘

TAG_RE = re.compile(r"<[^>]+>")
# 语雀导出是 <h5>3月（亏损15W）</h5>，剥标签后行首没有 #，故 #{0,6} 兼容两种写法
MONTH_RE = re.compile(r"^\s*#{0,6}\s*(\d{1,2})\s*月[^\n（]*（\s*([^）]*?)\s*）", re.M)
# 金额：15W / 9.5W / 2W5（=2万5）/ 5000 / 1.2W
AMOUNT_RE = re.compile(r"(?:亏损|盈利|赚|亏)?\s*(\d+(?:\.\d+)?)\s*W\s*(\d)?|(\d+(?:\.\d+)?)\s*(?:元|万)?")
EVENT_RE = re.compile(
    r"(?:最终|最后)?\s*(\d+(?:\.\d+)?(?:\s*[、,和]\s*\d+(?:\.\d+)?)*)\s*"
    r"(开仓|建仓|加仓|加多|减仓|平仓|止损|止盈|清仓)"
    r"(?:[（(]([^）)]*)[）)])?"
)
DATE_RE = re.compile(r"(?:(\d{4})[.\-/])?(\d{1,2})[.\-/](\d{1,2})")


def strip_tags(text):
    """去掉语雀导出的 HTML 标签，并把 markdown 强调符还原成纯文本。
    <br> 必须替换成空格而非直接删除，否则 'AU904<br/>put AG13000'
    会粘连成 'AU904put AG13000'，导致只识别出第一个品种。"""
    t = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    t = re.sub(r"</(p|div|h[1-6]|li|tr|table)>", "\n", t, flags=re.I)
    t = TAG_RE.sub("", t)
    t = t.replace("**", "").replace("_", "")
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def parse_amount(text):
    """'亏损15W' -> -150000；'赚1.5W' -> 15000；'2W5' -> 25000；'5000' -> 5000。
    返回 (数值, 原文片段)；解析不出返回 (None, None)。"""
    if not text:
        return None, None
    t = text.strip()
    neg = bool(re.search(r"亏损|亏", t))

    m = re.search(r"(\d+(?:\.\d+)?)\s*W\s*(\d)?", t)
    if m:
        base = float(m.group(1)) * 10000
        if m.group(2):  # 2W5 = 2万5千
            base += float(m.group(2)) * 1000
        return (-base if neg else base), m.group(0)

    m = re.search(r"(\d+(?:\.\d+)?)\s*万", t)
    if m:
        base = float(m.group(1)) * 10000
        return (-base if neg else base), m.group(0)

    m = re.search(r"(?:亏损|盈利|赚|亏)\s*(\d+(?:\.\d+)?)", t)
    if m:
        base = float(m.group(1))
        return (-base if neg else base), m.group(0)

    return None, None


def parse_events(text):
    """从 '1400开仓（开仓过早）1450加仓（亏损加仓）...最终1500、1555止损'
    还原操作序列。"""
    type_map = {
        "开仓": "open", "建仓": "open", "加仓": "add", "加多": "add",
        "减仓": "reduce", "平仓": "close", "止损": "close",
        "止盈": "close", "清仓": "close",
    }
    events = []
    for m in EVENT_RE.finditer(text or ""):
        price_raw, action, note = m.group(1), m.group(2), m.group(3) or ""
        prices = [p.strip() for p in re.split(r"[、,和]", price_raw) if p.strip()]
        for p in prices:
            try:
                price = float(p)
            except ValueError:
                continue
            events.append({
                "type": type_map.get(action, "other"),
                "action": action,
                "price": price,
                "note": note.strip(),
            })
    return events


def parse_table_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        raw = f.read()
    text = strip_tags(raw)

    # ---- 1. 月度汇总 ----
    months = []
    for m in MONTH_RE.finditer(text):
        month_no = int(m.group(1))
        label = m.group(2).strip()
        pnl, _ = parse_amount(label)
        months.append({
            "month": f"{YEAR}-{month_no:02d}",
            "label": f"{month_no}月",
            "pnlText": label,
            "pnl": pnl,
        })

    # ---- 2. 按月份切块，分别处理表格与叙述 ----
    # 定位每个月份标题在文本中的位置
    anchors = [(m.start(), int(m.group(1))) for m in MONTH_RE.finditer(text)]
    anchors.append((len(text), None))

    trades = []
    narratives = []
    seq = 0

    for idx in range(len(anchors) - 1):
        start, month_no = anchors[idx]
        end = anchors[idx + 1][0]
        block = text[start:end]
        month_key = f"{YEAR}-{month_no:02d}" if month_no else None

        lines = [l.rstrip() for l in block.split("\n")]
        # 表格块：连续以 | 开头的行
        table_lines = [l for l in lines if l.strip().startswith("|")]
        is_table_block = len(table_lines) >= 3

        if is_table_block:
            header = parse_table_row(table_lines[0])
            for row in table_lines[2:]:  # 跳过表头与分隔行
                cells = parse_table_row(row)
                if not cells or not any(cells):
                    continue
                desc = cells[0]
                if not desc or set(desc) <= set("-: "):
                    continue
                hits = find_varieties(desc)
                # 一个格子里挤了多个品种（如 "call AU904 put AG13000"）时拆成多条，
                # 共享归因与原文，pnl 记在整批上不拆分
                pnl, pnl_raw = parse_amount(desc)
                events = parse_events(desc)

                # 归因：表头与单元格一一对应
                attribution = {}
                for h, c in zip(header[1:], cells[1:]):
                    if h and c:
                        attribution[h] = c

                # 方向
                direction = None
                if "做空" in desc or "空" in desc and "做多" not in desc:
                    direction = "空"
                elif "做多" in desc or "多" in desc:
                    direction = "多"

                if not hits:
                    hits = [("", None)]
                for zh, code in hits:
                    seq += 1
                    inst = parse_instrument(desc, variety=zh or None, code=code)
                    trades.append({
                        "id": f"md-t{seq:03d}",
                        "source": "月度复盘md",
                        "month": month_key,
                        "variety": zh,
                        "symbol": code,
                        "contract": inst["contract"],
                        "strike": inst["strike"],
                        "instrumentType": inst["instrumentType"],
                        "optionType": inst["optionType"],
                        "moneyness": inst["moneyness"],
                        "direction": direction,
                        "pnlText": pnl_raw or "",
                        "pnl": pnl,
                        "attribution": attribution,
                        "events": events,
                        "raw": desc,
                    })
        else:
            # 叙述块：逐条 bullet / 行做宽松提取
            for line in lines:
                s = line.strip().lstrip("-+*_ ").strip()
                if len(s) < 4:
                    continue
                if s.startswith("![]") or s.startswith("http"):
                    continue
                dm = DATE_RE.search(s)
                date = ""
                if dm:
                    y = dm.group(1) or str(YEAR)
                    date = f"{y}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                hits = find_varieties(s)
                zh, code = hits[0] if hits else ("", None)
                pnl, pnl_raw = parse_amount(s)
                # 只保留含品种或盈亏的行，避免把纯反思句也塞进记录
                if not (zh or pnl is not None):
                    continue
                seq += 1
                narratives.append({
                    "id": f"md-n{seq:03d}",
                    "source": "月度复盘md",
                    "month": month_key,
                    "date": date,
                    "variety": zh,
                    "symbol": code,
                    "pnlText": pnl_raw or "",
                    "pnl": pnl,
                    "text": s,
                })

    payload = {
        "source": "月度复盘md",
        "sourceFile": SRC,
        "year": YEAR,
        "note": "金额口径：'2W5'=25000，'15W'=150000。归因字段沿用原表列名。",
        "months": months,
        "trades": trades,
        "narratives": narratives,
        "count": {"months": len(months), "trades": len(trades), "narratives": len(narratives)},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"months={len(months)} trades={len(trades)} narratives={len(narratives)}")
    print(f"out={OUT}")


if __name__ == "__main__":
    main()
