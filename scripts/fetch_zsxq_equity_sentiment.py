"""Build a bounded A-share sentiment snapshot from the Trend Mini App group.

Only sanitized text excerpts and aggregate counts are persisted. Authentication
stays inside zsxq-cli's keychain; signed media URLs and tokens are never written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path.cwd()
RUN_DATE = os.environ.get("REPORT_DATE", datetime.now().strftime("%Y%m%d"))
TARGET_DATE = f"{RUN_DATE[:4]}-{RUN_DATE[4:6]}-{RUN_DATE[6:]}"
GROUP_ID = os.environ.get("ZSXQ_TREND_GROUP_ID", "88885185558542")
NICK_USER_ID = os.environ.get("ZSXQ_TREND_OWNER_ID", "15555852544122")
OUT_ROWS = ROOT / "data" / f"zsxq_equity_sentiment_{RUN_DATE}.csv"
OUT_SUMMARY = ROOT / "data" / f"zsxq_equity_sentiment_summary_{RUN_DATE}.json"

BULLISH_WORDS = (
    "加仓", "补仓", "建仓", "抄底", "做多", "看多", "买入", "反弹", "修复",
    "回暖", "突破", "上涨", "涨停", "强势", "进场", "增持",
)
BEARISH_WORDS = (
    "减仓", "清仓", "退场", "卖出", "止损", "做空", "看空", "下跌", "跌停",
    "寒", "凉", "风险", "危险", "可怕", "保住本金", "出货", "割了", "弱势",
    "休息", "低仓位", "仓位应该非常低", "可做的个股应该非常少", "最保守",
)


def cli_path() -> str:
    found = shutil.which("zsxq-cli.cmd") or shutil.which("zsxq-cli")
    if not found:
        raise RuntimeError("zsxq-cli is not installed or not on PATH")
    return found


def run_cli(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [cli_path(), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"zsxq-cli failed: {detail[:300]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("zsxq-cli returned non-JSON output") from exc
    if payload.get("ok") is False or payload.get("success") is False:
        raise RuntimeError(f"zsxq-cli API error: {str(payload.get('error', payload))[:300]}")
    return payload


def clean_text(value: object, limit: int = 240) -> str:
    text = re.sub(r"<e\b[^>]*?/?>", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def created_on_target(value: object) -> bool:
    return str(value or "").startswith(TARGET_DATE)


def comment_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("comments", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            for nested_key in ("comments", "items"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]
    return []


def owner_info(item: dict[str, Any]) -> tuple[str, str]:
    owner = item.get("owner") or item.get("user") or {}
    if not isinstance(owner, dict):
        owner = {}
    return str(owner.get("name") or owner.get("alias") or "匿名"), str(owner.get("user_id") or "")


def item_text(item: dict[str, Any]) -> str:
    for key in ("content", "text", "comment", "title"):
        if item.get(key):
            return clean_text(item.get(key))
    return ""


def classify(text: str) -> tuple[str, int, int]:
    if not text:
        return "neutral", 0, 0
    bull = sum(text.count(word) for word in BULLISH_WORDS)
    bear = sum(text.count(word) for word in BEARISH_WORDS)
    if "美股" in text and not any(word in text for word in ("A股", "大盘", "科创", "创业板", "恒生", "恒科")):
        return "neutral", bull, bear
    if bull > bear:
        return "bullish", bull, bear
    if bear > bull:
        return "bearish", bull, bear
    return "neutral", bull, bear


def make_row(item: dict[str, Any], item_type: str, topic_id: str) -> dict[str, Any] | None:
    text = item_text(item)
    if not text:
        return None
    author, user_id = owner_info(item)
    sentiment, bull_hits, bear_hits = classify(text)
    created_at = str(item.get("create_time") or item.get("created_at") or "")
    return {
        "data_date": TARGET_DATE,
        "created_at": created_at,
        "item_type": item_type,
        "topic_id": topic_id,
        "author": author,
        "is_nick": user_id == NICK_USER_ID,
        "sentiment": sentiment,
        "bullish_hits": bull_hits,
        "bearish_hits": bear_hits,
        "excerpt": text,
        "source": "知识星球·趋势小程序",
    }


def build_summary(rows: pd.DataFrame, status: str, error: str = "") -> dict[str, Any]:
    if rows.empty:
        return {
            "source": "知识星球·趋势小程序",
            "data_date": TARGET_DATE,
            "status": status,
            "sample_count": 0,
            "topic_count": 0,
            "comment_count": 0,
            "nick_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "sentiment_score": 0,
            "sentiment_label": "样本不足",
            "confidence": "低",
            "community_summary": "当日未取得可用样本。",
            "nick_summary": "当日未发现 Nick 的发帖或回复。",
            "methodology": "普通样本权重1，Nick样本权重2；仅按显式方向词计分。",
            "error": clean_text(error, 300),
        }

    weighted = rows.assign(weight=rows["is_nick"].map({True: 2.0, False: 1.0}))
    bull_weight = weighted.loc[weighted["sentiment"] == "bullish", "weight"].sum()
    bear_weight = weighted.loc[weighted["sentiment"] == "bearish", "weight"].sum()
    directional = bull_weight + bear_weight
    score = round(100 * (bull_weight - bear_weight) / directional) if directional else 0
    if directional < 3:
        label = "样本不足"
    elif score >= 35:
        label = "风险偏好偏高"
    elif score >= 10:
        label = "风险偏好中性偏高"
    elif score <= -35:
        label = "风险偏好偏低"
    elif score <= -10:
        label = "风险偏好中性偏低"
    else:
        label = "风险偏好中性"
    confidence = "高" if len(rows) >= 15 and directional >= 8 else ("中" if len(rows) >= 6 and directional >= 3 else "低")

    bull_count = int((rows["sentiment"] == "bullish").sum())
    bear_count = int((rows["sentiment"] == "bearish").sum())
    neutral_count = int((rows["sentiment"] == "neutral").sum())
    community_summary = (
        f"当日样本{len(rows)}条：偏多{bull_count}、偏空{bear_count}、中性{neutral_count}；"
        f"按方向词加权后为{label}，置信度{confidence}。"
    )
    nick_rows = rows[rows["is_nick"]]
    nick_summary = "当日未发现 Nick 的发帖或回复。"
    if not nick_rows.empty:
        nick_text = " ".join(nick_rows["excerpt"].tolist())
        nick_points = []
        if "休息" in nick_text:
            nick_points.append("回复中明确提到可以休息、什么都不做")
        if "仓位应该" in nick_text or "可做的个股" in nick_text:
            nick_points.append("认为当前固定股池可做标的很少，按纪律仓位应较低、以试仓为主")
        if "做空" in nick_text:
            nick_points.append("说明当前做空看板与反向信号仍较粗糙，后续会完善显示和 API 指标")
        nick_summary = "；".join(nick_points) if nick_points else "；".join(nick_rows["excerpt"].head(2).tolist())

    evidence = []
    for sentiment in ("bearish", "bullish", "neutral"):
        part = rows[rows["sentiment"] == sentiment]
        for excerpt in part["excerpt"].head(2):
            evidence.append({"sentiment": sentiment, "excerpt": excerpt})

    return {
        "source": "知识星球·趋势小程序",
        "data_date": TARGET_DATE,
        "status": status,
        "sample_count": int(len(rows)),
        "topic_count": int((rows["item_type"] == "topic").sum()),
        "comment_count": int((rows["item_type"] == "comment").sum()),
        "nick_count": int(rows["is_nick"].sum()),
        "bullish_count": bull_count,
        "bearish_count": bear_count,
        "neutral_count": neutral_count,
        "sentiment_score": int(score),
        "sentiment_label": label,
        "confidence": confidence,
        "community_summary": community_summary,
        "nick_summary": nick_summary,
        "evidence": evidence,
        "methodology": "普通样本权重1，Nick样本权重2；只按当日帖子和评论中的显式风险偏好词计分，不代表全市场情绪。",
        "error": clean_text(error, 300),
    }


def main() -> None:
    OUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    status = "ok"
    error = ""
    try:
        auth = run_cli(["auth", "status", "--json"])
        if not bool((auth.get("data") or {}).get("loggedIn")):
            raise RuntimeError("zsxq-cli is not logged in")
        topics_payload = run_cli(["group", "+topics", "--group-id", GROUP_ID, "--limit", "30", "--json"])
        topics = topics_payload.get("topics_brief") or topics_payload.get("topics") or []
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            topic_id = str(topic.get("topic_id") or "")
            if created_on_target(topic.get("create_time")):
                row = make_row(topic, "topic", topic_id)
                if row:
                    rows.append(row)
            counts = topic.get("counts") or {}
            if not topic_id or not int(counts.get("comments") or 0):
                continue
            payload = run_cli(
                [
                    "api", "call", "get_topic_comments", "--params",
                    json.dumps({"topic_id": topic_id, "count": 50, "index": 0}, ensure_ascii=False),
                ]
            )
            for comment in comment_list(payload):
                if not created_on_target(comment.get("create_time") or comment.get("created_at")):
                    continue
                row = make_row(comment, "comment", topic_id)
                if row:
                    rows.append(row)
    except Exception as exc:
        status = "degraded"
        error = str(exc)

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(["item_type", "topic_id", "author", "created_at", "excerpt"])
        frame = frame.sort_values("created_at", ascending=False)
    else:
        frame = pd.DataFrame(
            columns=[
                "data_date", "created_at", "item_type", "topic_id", "author", "is_nick",
                "sentiment", "bullish_hits", "bearish_hits", "excerpt", "source",
            ]
        )
    summary = build_summary(frame, status, error)
    frame.to_csv(OUT_ROWS, index=False, encoding="utf-8-sig")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"zsxq sentiment rows: {OUT_ROWS}")
    print(f"zsxq sentiment summary: {OUT_SUMMARY}")
    print(f"status={status}; samples={len(frame)}; nick={summary['nick_count']}; label={summary['sentiment_label']}")


if __name__ == "__main__":
    main()
