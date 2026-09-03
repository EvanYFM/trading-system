# -*- coding: utf-8 -*-
"""把用户在网页上「📤 导出我的复盘」下载的 JSON 合并进前端静态数据。

用法（在仓库根目录执行）：
    python scripts/merge_user_journal.py <导出的json路径>

例如：
    python scripts/merge_user_journal.py "C:/Users/29266/Desktop/user_journal_2026-09-03.json"

行为：
- 按 observation.id 去重，同名记录以「最新导出的版本」为准（可重复执行，不会重复添加）
- 结果写入 web/research_dashboard/data/imported/user_journal.json
- 该文件随 git 发布，页面初始化时自动加载（history-store.init）
"""
import json
import os
import sys
from datetime import datetime

TARGET = os.path.join("web", "research_dashboard", "data", "imported", "user_journal.json")


def main(src_path):
    if not os.path.exists(src_path):
        raise SystemExit(f"找不到导出文件：{src_path}")

    with open(src_path, "r", encoding="utf-8") as handle:
        incoming = json.load(handle)

    items = incoming.get("observations", [])
    if not items:
        print("导出文件里没有复盘记录，无需合并。")
        return

    existing_observations = []
    if os.path.exists(TARGET):
        with open(TARGET, "r", encoding="utf-8") as handle:
            existing_observations = json.load(handle).get("observations", [])

    merged = {item["id"]: item for item in existing_observations}
    added = 0
    for item in items:
        if item["id"] not in merged:
            added += 1
        merged[item["id"]] = item  # 同名记录以最新版本覆盖

    payload = {
        "source": "工作台日志",
        "note": "用户在工作台写的复盘，由 scripts/merge_user_journal.py 合并后随 git 发布",
        "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "count": len(merged),
        "observations": list(merged.values()),
    }
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print(f"合并完成：新增 {added} 条，累计 {len(merged)} 条 -> {TARGET}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法：python scripts/merge_user_journal.py <导出的json路径>")
    main(sys.argv[1])
