# -*- coding: utf-8 -*-
"""把历史交易日志 Excel 转成工作站可导入的结构化 JSON。

口径（用户 2026-09-01 确认）：
1. 仓位列为空 = 未执行交易，只是参考他人策略的观察记录。
2. 观察记录的「盈亏」列是策略方收益，不是本人的钱，单独存 strategyPnlText，
   绝不写入 myPnl。
3. 一行含多个品种的日内短线记录，拆成每品种一条；盈亏无法拆分则留空并标记。
4. 来源统一标 source="交易日志Excel"。
"""
import json
import re
from openpyxl import load_workbook

SRC = r"C:\Users\29266\Desktop\交易日志-20251031至20251113.xlsx"
OUT = r"C:\Users\29266\WorkBuddy\已有网站优化\trading-system-fresh\web\research_dashboard\data\imported\trading_log_excel.json"

# 品种中文名 -> 标准代码
VARIETY_CODE = {
    "沪金": "AU", "沪银": "AG", "沪铜": "CU", "沪铝": "AL", "沪锌": "ZN",
    "沪铅": "PB", "沪镍": "NI", "沪锡": "SN", "铂金": "PT", "钯金": "PD",
    "螺纹钢": "RB", "热卷": "HC", "铁矿石": "I", "焦煤": "JM", "焦炭": "J",
    "锰硅": "SM", "硅铁": "SF", "玻璃": "FG", "纯碱": "SA",
    "原油": "SC", "燃油": "FU", "低硫油": "LU", "低硫燃料油": "LU", "沥青": "BU",
    "LPG": "PG", "液化石油气": "PG",
    "甲醇": "MA", "乙二醇": "EG", "苯乙烯": "EB", "PTA": "TA", "PVC": "V",
    "塑料": "L", "聚丙烯": "PP", "PP": "PP", "天然橡胶": "RU", "橡胶": "RU",
    "纸浆": "SP", "尿素": "UR", "短纤": "PF", "瓶片": "PR", "纯苯": "BZ",
    "对二甲苯": "PX", "PX": "PX", "烧碱": "SH", "氧化铝": "AO", "合成橡胶": "BR",
    "豆粕": "M", "菜粕": "RM", "豆油": "Y", "棕榈油": "P", "菜油": "OI",
    "玉米": "C", "豆一": "A", "豆二": "B", "淀粉": "CS",
    "棉花": "CF", "白糖": "SR", "生猪": "LH", "鸡蛋": "JD", "苹果": "AP",
    "红枣": "CJ", "花生": "PK", "20号胶": "NR",
    "碳酸锂": "LC", "工业硅": "SI", "多晶硅": "PS",
    "集运欧线": "EC", "欧线": "EC",
}

# 代码 -> 中文名（反查，用于合约代码识别）
CODE_VARIETY = {}
for _zh, _code in VARIETY_CODE.items():
    CODE_VARIETY.setdefault(_code, _zh)

STRATEGY_SOURCES = ["赵大侠策略", "马师傅策略"]

DATE_RE = re.compile(r"(20\d{2})[.\-/年]\s?(\d{1,2})[.\-/月]\s?(\d{1,2})")


def cell_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_date(text):
    m = DATE_RE.search(text or "")
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return ""


def to_number(text):
    """'200' / '-1040' / '0.1333' -> float；非数字返回 None"""
    t = (text or "").strip().replace(",", "")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def find_varieties(*texts):
    """从若干文本里找出出现的品种，返回 [(中文名, 代码)] 去重列表。
    先匹配中文名；没有中文名时，再从英文合约代码反查（如 AU02 -> 沪金）。"""
    found = []
    seen = set()
    blob = "\n".join(t for t in texts if t)
    # 先匹配中文名（长的优先，避免"豆油"被"油"类误伤）
    for zh in sorted(VARIETY_CODE, key=len, reverse=True):
        if zh in blob and zh not in seen:
            seen.add(zh)
            found.append((zh, VARIETY_CODE[zh]))
    if found:
        return found
    # 中文名没命中时，从英文代码反查：AU02 / JM2701 / al2512
    for m in re.finditer(r"(?<![A-Za-z])([A-Za-z]{1,2})\s?-?\s?(\d{2,4})(?![A-Za-z])", blob):
        code = m.group(1).upper()
        if code in CODE_VARIETY and code not in seen:
            seen.add(code)
            found.append((CODE_VARIETY[code], code))
    if found:
        return found
    # 兜底：代码后没有数字的写法，如 "call SC,亏损6000"、"call eb,亏损1W"。
    # 只取独立成词的代码，避免把普通英文单词里的字母当成品种。
    for m in re.finditer(r"(?<![A-Za-z])([A-Za-z]{1,3})(?![A-Za-z])", blob):
        code = m.group(1).upper()
        if code in CODE_VARIETY and code not in seen:
            seen.add(code)
            found.append((CODE_VARIETY[code], code))
    return found


def detect_source(text):
    for s in STRATEGY_SOURCES:
        if s in text:
            return s
    return None


def _is_contract_month(num_str):
    """区分「合约月份」与「期权行权价」。
    - 合约月份：2 位（02/05/07）、3 位（601/904）、4 位且 25xx~30xx（2512/2601/2701）
    - 行权价：其余（call AU 1000 -> 1000、put AG13000 -> 13000）"""
    n = num_str
    if len(n) in (2, 3):
        return True
    if len(n) == 4 and n[:2] in ("25", "26", "27", "28", "29", "30"):
        return True
    return False


def parse_instrument(text, variety=None, code=None):
    """从 'call al2512虚3' / 'put期权虚3' / '多3手' / 'call沪铜02虚1'
    里识别工具类型、方向、期权类型、合约、虚值档位。

    variety / code 用于「按品种就近匹配合约」：一行含多个品种时，不能让
    所有品种共用第一个命中的合约（玻璃2601 + 纯碱2601 不能都写成 FG2601）。
    """
    t = (text or "").strip()
    out = {
        "instrumentType": None,  # 期货 / 期权
        "optionType": None,      # call / put
        "contract": None,        # 合约月份：JM2701 / al2512 / SH2511
        "strike": None,          # 期权行权价：call AU 1000 里的 1000
        "moneyness": None,       # 虚1 / 虚2-4 / 实值1
        "lots": None,
        "direction": None,       # 多 / 空
    }
    if not t:
        return out

    low = t.lower()
    if "call" in low:
        out["instrumentType"] = "期权"
        out["optionType"] = "call"
    elif "put" in low:
        out["instrumentType"] = "期权"
        out["optionType"] = "put"
    elif "期权" in t:
        out["instrumentType"] = "期权"
    elif re.search(r"多\s*\d*\s*手|空\s*\d*\s*手|^多$|^空$|期货", t):
        out["instrumentType"] = "期货"

    # 合约提取优先级：本品种名+数字 > 本品种代码+数字 > 通用英文代码+数字。
    # 品种名与数字之间允许夹 call/put/空格等少量字符（"烧碱call2511" -> SH2511）。
    def _assign(prefix, num):
        """同一个数字，在期货里是合约月份（JM2701），在期权里可能是行权价
        （call AU 1000 的 1000）。按位数与区间区分，避免把行权价写成合约号。"""
        if _is_contract_month(num):
            if not out["contract"]:
                out["contract"] = f"{prefix}{num}"
        elif not out["strike"]:
            out["strike"] = num

    m = None
    if variety:
        m = re.search(re.escape(variety) + r"[^\d]{0,8}?(\d{2,5})(?!\d)", t)
        if m:
            _assign(code or "", m.group(1))
    if not out["contract"] and not out["strike"] and code:
        m = re.search(r"(?<![A-Za-z])" + re.escape(code) + r"\s?-?\s?(\d{2,5})(?![A-Za-z])", t)
        if m:
            _assign(code, m.group(1))
    if not out["contract"] and not out["strike"]:
        # 通用英文代码 + 数字。两侧字母边界防止 "call2511" 里的 "ll" 被当成代码。
        m = re.search(r"(?<![A-Za-z])([A-Za-z]{1,3})\s?-?\s?(\d{2,5})(?![A-Za-z])", t)
        if m:
            _assign(m.group(1).upper(), m.group(2))
    if not out["contract"] and not out["strike"] and variety:
        # 兜底：中文品种名 + 数字（沪铜02 / 豆粕2601 / 碳酸锂601）
        for _zh in sorted(VARIETY_CODE, key=len, reverse=True):
            m2 = re.search(re.escape(_zh) + r"\s?(\d{2,5})", t)
            if m2:
                _assign(VARIETY_CODE[_zh], m2.group(1))
                break

    # 虚值档位
    m = re.search(r"(实值\s*\d|虚\s*\d(?:\s*[-~至]\s*\d)?)", t)
    if m:
        out["moneyness"] = m.group(1).replace(" ", "")

    # 手数
    m = re.search(r"(\d+)\s*手", t)
    if m:
        out["lots"] = int(m.group(1))

    # 方向
    if "空" in t and "多空" not in t:
        out["direction"] = "空"
    elif "多" in t:
        out["direction"] = "多"

    return out


def main():
    wb = load_workbook(SRC, data_only=True, read_only=True)
    ws = wb["交易日志"]

    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([cell_text(c) for c in row])
    rows = [r for r in rows if any(c for c in r)]
    body = rows[1:]  # 去掉表头

    # 先按「主行 + 附属评级行」配对
    blocks = []
    i = 0
    while i < len(body):
        row = body[i]
        if not row[0]:
            i += 1
            continue
        rec = {
            "品种列": row[0], "技术面": row[1], "基本面": row[2], "资金面": row[3],
            "政策面": row[4], "情绪面": row[5], "认知偏差": row[6], "综合评价": row[7],
            "交易策略": row[8], "止损止盈": row[9], "仓位": row[10], "盈亏": row[11],
            "比例": row[12], "复盘": row[13], "评级": {},
        }
        if i + 1 < len(body) and not body[i + 1][0]:
            nxt = body[i + 1]
            for key, idx in [("技术面", 1), ("基本面", 2), ("资金面", 3), ("政策面", 4),
                             ("情绪面", 5), ("认知偏差", 6), ("综合评价", 7)]:
                if idx < len(nxt) and nxt[idx]:
                    rec["评级"][key] = nxt[idx]
            i += 2
        else:
            i += 1
        blocks.append(rec)

    observations = []
    seq = 0
    last_date = ""
    last_label = ""

    for b in blocks:
        variety_cell = b["品种列"]
        strategy_cell = b["交易策略"]
        position = (b["仓位"] or "").strip()
        pnl_text = b["盈亏"]
        # 用户口径：仓位列「空」= 未执行；非空（含 "1手call" 这类文本）= 已执行
        executed = bool(position)

        date = parse_date(variety_cell)
        date_note = ""
        if not date:
            # 原表承接行未单独标注日期：留空不猜测，只记录上一行信息供排序参考
            date_note = f"原表未标注日期；上一行记录为 {last_label}（{last_date or '无日期'}）"
        else:
            last_date = date

        strategy_source = detect_source(variety_cell) or detect_source(strategy_cell)
        if "自己" in variety_cell:
            strategy_source = "自己"
        if not strategy_source:
            strategy_source = "自己"  # 未标注外部策略源，即本人自主判断

        # 工具信息可能写在品种列（如 "call沪铜02虚1"）、交易策略列或技术面列，合并解析。
        # 注意：具体解析要等品种确定后按品种就近匹配合约，见下方循环内。
        inst_blob = " ".join(x for x in [variety_cell, strategy_cell, b["技术面"]] if x)

        # 是否「一行多品种」的日内短线：品种列含"短线"，或复盘里命中 >=2 个品种
        hits = find_varieties(variety_cell, b["技术面"], " ".join(b["评级"].values()),
                              strategy_cell, b["复盘"])
        is_batch = ("短线" in variety_cell) or len(hits) >= 2

        if is_batch and hits:
            # 拆成每品种一条；盈亏无法拆分，留空并标记
            for zh, code in hits:
                seq += 1
                # 每个品种单独解析工具，避免多品种共用第一个命中的合约
                inst = parse_instrument(inst_blob, variety=zh, code=code)
                observations.append(build_obs(
                    seq, date, date_note, zh, code, strategy_source, inst, b,
                    position=None, my_pnl=None, ratio=None,
                    # 观察类保留策略方收益原文（它不进 myPnl，不会污染盈亏统计）
                    strategy_pnl_text=pnl_text,
                    batch_flag=True, executed=False,
                ))
        else:
            seq += 1
            zh, code = hits[0] if hits else (clean_variety_name(variety_cell), None)
            inst = parse_instrument(inst_blob, variety=zh, code=code)
            my_pnl = to_number(pnl_text) if executed else None
            strat_pnl = "" if executed else pnl_text
            observations.append(build_obs(
                seq, date, date_note, zh, code, strategy_source, inst, b,
                position=to_number(position), my_pnl=my_pnl,
                ratio=to_number(b["比例"]) if executed else None,
                strategy_pnl_text=strat_pnl,
                batch_flag=False, executed=executed,
            ))
        last_label = f"{zh if not (is_batch and hits) else '/'.join(h[0] for h in hits)}"

    observations.sort(key=lambda x: (x["date"] or "9999-99-99", x["seq"]))

    payload = {
        "source": "交易日志Excel",
        "sourceFile": SRC,
        "note": "仓位列空=观察他人策略、未执行；此类记录的 strategyPnlText 为策略方收益，非本人盈亏",
        "count": len(observations),
        "observations": observations,
    }
    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    executed_n = sum(1 for o in observations if o["executed"])
    print(f"total={len(observations)} executed={executed_n} observe={len(observations) - executed_n}")
    print(f"out={OUT}")


def clean_variety_name(cell):
    """去掉日期与策略来源，剩下品种描述。"""
    t = DATE_RE.sub("", cell or "")
    for s in STRATEGY_SOURCES:
        t = t.replace(s, "")
    t = t.replace("自己", "").replace("夜盘", "").replace("日盘", "")
    return t.strip().replace("\n", " ")[:40]


def build_obs(seq, date, date_note, variety, code, strategy_source, inst, b,
              position, my_pnl, ratio, strategy_pnl_text, batch_flag, executed):
    return {
        "seq": seq,
        "id": f"excel-{seq:03d}",
        "source": "交易日志Excel",
        "date": date,
        "dateNote": date_note,
        "isBatchSplit": batch_flag,
        # 批次拆分时保留原始整批的仓位/盈亏供参考，但 myPnl 留空避免虚假统计
        "batchPosition": (b["仓位"] or "").strip() if batch_flag else "",
        "batchPnl": (b["盈亏"] or "").strip() if batch_flag else "",
        "variety": variety,
        "symbol": code,
        "contract": inst["contract"],
        "strike": inst["strike"],
        "instrumentType": inst["instrumentType"],
        "optionType": inst["optionType"],
        "moneyness": inst["moneyness"],
        "direction": inst["direction"],
        "lots": inst["lots"],
        "strategySource": strategy_source,
        "executed": executed,
        "position": position,
        "myPnl": my_pnl,
        "pnlRatio": ratio,
        "strategyPnlText": strategy_pnl_text,
        "pnlNote": "日内短线批次，盈亏无法拆分到单品种" if batch_flag else "",
        "technical": b["技术面"],
        "fundamental": b["基本面"],
        "capital": b["资金面"],
        "policy": b["政策面"],
        "sentiment": b["情绪面"],
        "cognitiveBias": b["认知偏差"],
        "overall": b["综合评价"],
        "ratings": b["评级"],
        "strategy": b["交易策略"],
        "stopLossTakeProfit": b["止损止盈"],
        "review": b["复盘"],
    }


if __name__ == "__main__":
    main()
