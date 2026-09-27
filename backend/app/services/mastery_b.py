"""Mastery persistence helpers (part 2)."""
from __future__ import annotations
from datetime import datetime, timezone
from app.database.connection import _transaction, get_connection
from app.services.mastery_a import _diff_w, score_row


def record_attempt(uid, concept, correct, difficulty="MEDIUM", subject="") -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    key = str(concept or "").strip()[:200] or "general"

    def work(c):
        r = c.execute("SELECT * FROM concept_mastery WHERE user_id=? AND concept_key=?",
                      (int(uid), key)).fetchone()
        d = dict(r) if r else {"attempts": 0, "correct": 0, "streak": 0,
                               "best_streak": 0, "difficulty_sum": 0.0,
                               "last_correct": 0}
        att = int(d.get("attempts", 0)) + 1
        cor = int(d.get("correct", 0)) + (1 if correct else 0)
        streak = int(d.get("streak", 0)) + 1 if correct else 0
        best = max(int(d.get("best_streak", 0)), streak)
        dsum = float(d.get("difficulty_sum", 0)) + _diff_w(difficulty)
        acc = cor / att
        tmp = {"attempts": att, "correct": cor, "streak": streak,
               "best_streak": best, "difficulty_sum": dsum,
               "last_correct": 1 if correct else 0, "last_attempt_at": now}
        mastery, _ = score_row(tmp)
        c.execute(
            """INSERT INTO concept_mastery (user_id, concept_key, subject_slug,
            accuracy, attempts, correct, streak, best_streak, difficulty_sum,
            last_correct, last_attempt_at, mastery, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, concept_key) DO UPDATE SET subject_slug=excluded.subject_slug,
            accuracy=excluded.accuracy, attempts=excluded.attempts, correct=excluded.correct,
            streak=excluded.streak, best_streak=excluded.best_streak,
            difficulty_sum=excluded.difficulty_sum, last_correct=excluded.last_correct,
            last_attempt_at=excluded.last_attempt_at, mastery=excluded.mastery,
            updated_at=CURRENT_TIMESTAMP""",
            (int(uid), key, str(subject or "")[:120], round(acc, 4), att, cor,
             streak, best, round(dsum, 3), 1 if correct else 0, now,
             mastery))
    _transaction(work)
    return get_concept(uid, key)


def get_concept(uid, concept) -> dict | None:
    c = get_connection()
    r = c.execute("SELECT * FROM concept_mastery WHERE user_id=? AND concept_key=?",
                  (int(uid), str(concept))).fetchone()
    c.close()
    if not r:
        return None
    d = dict(r)
    m, parts = score_row(d)
    d["mastery"] = m
    d["signals"] = parts
    return d


def list_mastery(uid, limit=100) -> list[dict]:
    c = get_connection()
    rows = c.execute("SELECT * FROM concept_mastery WHERE user_id=? ORDER BY mastery ASC, updated_at DESC LIMIT ?",
                     (int(uid), max(1, min(int(limit or 50), 200)))).fetchall()
    c.close()
    out = []
    for r in rows:
        d = dict(r)
        m, parts = score_row(d)
        d["mastery"] = m
        d["signals"] = parts
        out.append(d)
    return out


def weak_concepts(uid, threshold=60.0, limit=10) -> list[dict]:
    return [m for m in list_mastery(uid, 200) if m["mastery"] < float(threshold)][:limit]
