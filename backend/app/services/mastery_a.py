"""Explainable concept mastery: accuracy + consistency + difficulty + recency."""
from __future__ import annotations
from datetime import datetime, timezone
from app.database.connection import _transaction, get_connection

DIFF_W = {"FOUNDATION": 0.6, "EASY": 0.8, "MEDIUM": 1.0, "HARD": 1.2,
          "BOARD_LEVEL": 1.25, "CHALLENGE": 1.4, "BEGINNER": 0.7, "ADVANCED": 1.3}


def _diff_w(d):
    return DIFF_W.get(str(d or "MEDIUM").upper(), 1.0)


def _recency(last_at):
    if not last_at:
        return 0.5
    try:
        ts = str(last_at).replace("T", " ")
        dt = datetime.fromisoformat(ts[:19])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
        if days <= 1:
            return 1.0
        if days <= 3:
            return 0.9
        if days <= 7:
            return 0.75
        if days <= 21:
            return 0.55
        return 0.35
    except Exception:
        return 0.5


def score_row(r: dict) -> tuple[float, dict]:
    att = max(1, int(r.get("attempts", 0) or 0))
    acc = float(r.get("correct", 0) or 0) / att
    streak = int(r.get("streak", 0) or 0)
    best = max(1, int(r.get("best_streak", 0) or streak or 1))
    consistency = min(1.0, streak / max(3.0, float(best)))
    if att <= 1:
        consistency = 0.5 if int(r.get("last_correct", 0)) else 0.2
    diff = float(r.get("difficulty_sum", 0) or 0) / att
    diff_n = max(0.0, min(1.0, (diff - 0.6) / 0.8))
    rec = _recency(r.get("last_attempt_at"))
    completion = 1.0 if att >= 3 else (0.5 if att == 2 else 0.25)
    mastery = round(100 * (0.45 * acc + 0.2 * consistency + 0.15 * diff_n
                           + 0.1 * rec + 0.1 * completion), 1)
    parts = {"accuracy": round(acc, 3), "consistency": round(consistency, 3),
             "difficulty": round(diff_n, 3), "recency": round(rec, 3),
             "completion": completion}
    return mastery, parts
