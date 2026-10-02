"""Gamification: XP only for meaningful learning actions."""
from __future__ import annotations
from app.database.connection import _transaction, get_connection

XP_RULES = {"lesson_completed": 50, "practice": 10, "quiz_correct": 10,
            "quiz_completed": 25, "mastery_up": 30, "project": 100,
            "note_created": 5, "revision": 15, "mission_completed": 60,
            "session_completed": 20}

LEVEL_XP = 250


def _level(xp: int) -> int:
    return max(1, int(xp // LEVEL_XP) + 1)


def award(uid: int, action: str, ref: str = "") -> dict:
    pts = int(XP_RULES.get(action, 0))
    if pts <= 0:
        return {"awarded": 0}

    def work(c):
        c.execute("""INSERT INTO gamification (user_id, xp, level, streak_days,
            last_active_date) VALUES (?, 0, 1, 0, '')
            ON CONFLICT(user_id) DO NOTHING""", (int(uid),))
        r = c.execute("SELECT xp FROM gamification WHERE user_id=?",
                      (int(uid),)).fetchone()
        xp = int((r["xp"] if r else 0) or 0) + pts
        c.execute("UPDATE gamification SET xp=?, level=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                  (xp, _level(xp), int(uid)))
        c.execute("INSERT INTO xp_events (user_id, action, points, ref) VALUES (?, ?, ?, ?)",
                  (int(uid), action[:80], pts, str(ref)[:180]))
        return _level(xp - pts), _level(xp)
    previous_level, level = _transaction(work)
    # A level change is a real persisted event; notify once, never per keystroke.
    if level > previous_level:
        try:
            from app.services.notifications import notify

            notify(int(uid), "level_up", f"Level {level} reached",
                   f"You earned {pts} XP for {action.replace('_', ' ')}.", href="/profile")
        except Exception:
            pass
    return profile(uid, awarded=pts)


def profile(uid: int, awarded: int = 0) -> dict:
    c = get_connection()
    r = c.execute("SELECT * FROM gamification WHERE user_id=?", (int(uid),)).fetchone()
    c.close()
    xp = int(dict(r)["xp"]) if r else 0
    lvl = _level(xp)
    return {"xp": xp, "level": lvl, "xp_next": lvl * LEVEL_XP,
            "awarded": awarded}
