"""Learner profile store (educational state only, no sensitive PII)."""
from __future__ import annotations
import json
from app.database.connection import _transaction, get_connection

LEVELS = {"school", "college", "competitive", "professional", "researcher", "other"}
PATHWAYS = {"school", "college", "competitive", "gate", "industrial",
            "research", "career", "custom"}
DIFFS = {"beginner", "easy", "medium", "hard", "advanced"}
STYLES = {"visual", "reading", "practice", "video", "mixed"}


def _s(v, n=120):
    return str(v or "").strip()[:n]


def _lst(v, n=20, m=80):
    out = []
    if isinstance(v, (list, tuple)):
        for i in v[:n]:
            t = str(i or "").strip()[:m]
            if t and t not in out:
                out.append(t)
    return out


def get_profile(uid: int) -> dict:
    c = get_connection()
    r = c.execute("SELECT * FROM learner_profiles WHERE user_id=?", (int(uid),)).fetchone()
    c.close()
    base = {"user_id": int(uid), "education_level": "school", "pathway": "school",
            "goals": [], "target_exam": "", "target_career": "", "subjects": [],
            "interests": [], "skill_levels": {}, "learning_style": "mixed",
            "daily_target_min": 30, "weekly_target_min": 180, "available_time": "",
            "preferred_difficulty": "medium", "preferences": {}}
    if not r:
        return base
    d = dict(r)
    for k in ("goals", "subjects", "interests"):
        try:
            base[k] = json.loads(d.get(k + "_json") or "[]")
        except Exception:
            base[k] = []
    for k in ("skill_levels", "preferences"):
        try:
            base[k] = json.loads(d.get(k + "_json") or "{}")
        except Exception:
            base[k] = {}
    for k in ("education_level", "pathway", "target_exam", "target_career",
              "learning_style", "available_time", "preferred_difficulty"):
        base[k] = d.get(k) or base[k]
    for k in ("daily_target_min", "weekly_target_min"):
        try:
            base[k] = int(d.get(k) or base[k])
        except Exception:
            pass
    return base


def save_profile(uid: int, p: dict) -> dict:
    lvl = _s(p.get("education_level"), 40).lower() or "school"
    if lvl not in LEVELS:
        raise ValueError("Invalid education_level.")
    path = _s(p.get("pathway"), 40).lower() or "school"
    if path not in PATHWAYS:
        raise ValueError("Invalid pathway.")
    pref = _s(p.get("preferred_difficulty"), 20).lower() or "medium"
    if pref not in DIFFS:
        raise ValueError("Invalid preferred_difficulty.")
    sty = _s(p.get("learning_style"), 20).lower() or "mixed"
    if sty not in STYLES:
        raise ValueError("Invalid learning_style.")
    try:
        daily = max(5, min(480, int(p.get("daily_target_min", 30))))
    except Exception:
        raise ValueError("daily_target_min must be a number.")
    try:
        weekly = max(15, min(3000, int(p.get("weekly_target_min", 180))))
    except Exception:
        raise ValueError("weekly_target_min must be a number.")
    skills = p.get("skill_levels") if isinstance(p.get("skill_levels"), dict) else {}
    skills = {str(k)[:80]: str(v)[:40] for k, v in list(skills.items())[:40]}
    prefs = p.get("preferences") if isinstance(p.get("preferences"), dict) else {}
    vals = (lvl, path, json.dumps(_lst(p.get("goals"))), _s(p.get("target_exam")),
            _s(p.get("target_career")), json.dumps(_lst(p.get("subjects"))),
            json.dumps(_lst(p.get("interests"))), json.dumps(skills), sty,
            daily, weekly, _s(p.get("available_time")), pref, json.dumps(prefs))

    def work(c):
        c.execute(
            """INSERT INTO learner_profiles (user_id, education_level, pathway,
            goals_json, target_exam, target_career, subjects_json, interests_json,
            skill_levels_json, learning_style, daily_target_min, weekly_target_min,
            available_time, preferred_difficulty, preferences_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET education_level=excluded.education_level,
            pathway=excluded.pathway, goals_json=excluded.goals_json,
            target_exam=excluded.target_exam, target_career=excluded.target_career,
            subjects_json=excluded.subjects_json, interests_json=excluded.interests_json,
            skill_levels_json=excluded.skill_levels_json,
            learning_style=excluded.learning_style,
            daily_target_min=excluded.daily_target_min,
            weekly_target_min=excluded.weekly_target_min,
            available_time=excluded.available_time,
            preferred_difficulty=excluded.preferred_difficulty,
            preferences_json=excluded.preferences_json, updated_at=CURRENT_TIMESTAMP""",
            (int(uid),) + vals)
    _transaction(work)
    return get_profile(uid)

