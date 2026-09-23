"""End-to-end live-server verification of the auth fixes + teacher-student connection.

Run: venv/Scripts/python.exe backend/_e2e_verify.py   (server must be on :5000)
"""
import json
import random
import sqlite3
import urllib.request
import urllib.error
import http.cookiejar

BASE = "http://localhost:5000"
SUFFIX = f"e2e{random.randint(1000, 9999)}"
TEACHER_EMAIL = f"{SUFFIX}-teacher@example.com"
STUDENT_EMAIL = f"{SUFFIX}-student@example.com"
PASSWORD = "Password123!"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(path, data=None, method=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, method=method or ("POST" if body else "GET"))
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode() or "{}")
        except Exception:
            payload = {}
        return exc.code, payload


results = []


def check(name, condition, extra=""):
    results.append((name, bool(condition)))
    print(("PASS" if condition else "FAIL"), "-", name, ("| " + str(extra)[:200] if extra and not condition else ""))


# --- 1. Corrupt-hash existing account must answer with a clean 401 ---
status, payload = call("/auth/login", {"email": "aitest@example.com", "password": "Anything@1"})
check("corrupt-hash existing account -> clean 401 (was 500 risk)",
      status == 401 and payload.get("code") == "INVALID_CREDENTIALS", (status, payload))

# --- 2. Teacher registers and creates a class ---
status, payload = call("/auth/register", {"name": "E2E Teacher", "email": TEACHER_EMAIL,
                                          "password": PASSWORD, "account_type": "teacher"})
check("teacher registers", status == 201 and payload.get("user", {}).get("role") == "TEACHER", payload)

status, payload = call("/api/v1/teacher/classes", {"name": f"E2E Class {SUFFIX}"})
check("teacher creates class", status == 201, payload)
class_id = payload.get("item", {}).get("id")

# --- 3. Student registers -> auto-registered with the teacher ---
call("/auth/logout")
status, payload = call("/auth/register", {"name": "E2E Student", "email": STUDENT_EMAIL,
                                          "password": PASSWORD, "account_type": "student"})
check("student registers", status == 201, payload)
auto_nested = (payload.get("data") or {}).get("auto_registered") or payload.get("auto_registered") or 0
check("student auto-registered to teacher", auto_nested >= 1, payload)

# --- 4. Teacher sees pending request and approves it ---
call("/auth/logout")
status, payload = call("/auth/login", {"email": TEACHER_EMAIL, "password": PASSWORD, "portal": "teacher"})
check("teacher logs in", status == 200, payload)

status, payload = call("/api/v1/teacher/join-requests")
items = [i for i in payload.get("items", []) if i.get("email") == STUDENT_EMAIL]
check("join request appears in teacher queue", len(items) == 1, payload)
request_id = items[0]["id"] if items else None

status, payload = call(f"/api/v1/teacher/join-requests/{request_id}/approve", {"class_id": class_id})
check("teacher approves join request", status == 200, payload)

status, payload = call(f"/api/v1/teacher/classes/{class_id}/students")
check("student now in class roster", any(m.get("email") == STUDENT_EMAIL for m in payload.get("items", [])), payload)

# --- 5. Teacher connects via announcement + assignment ---
status, payload = call("/api/v1/teacher/announcements", {"class_id": class_id, "message": f"E2E notice {SUFFIX}"})
check("announcement sent to class", status == 201, payload)
status, payload = call("/api/v1/teacher/assignments", {"class_id": class_id, "resource_type": "lesson",
                                                       "resource_id": "photo-lab", "title": f"E2E Homework {SUFFIX}",
                                                       "due_at": "2099-06-01 10:00:00"})
check("assignment sent to class", status == 201, payload)

# --- 6. Student receives both ---
call("/auth/logout")
status, payload = call("/auth/login", {"email": STUDENT_EMAIL, "password": PASSWORD, "portal": "student"})
check("student logs in", status == 200, payload)

status, payload = call("/api/v1/assignments")
check("assignment visible to student", any(a.get("title") == f"E2E Homework {SUFFIX}" for a in payload.get("items", [])), payload)
status, payload = call("/api/v1/announcements")
check("announcement visible to student", any(a.get("message") == f"E2E notice {SUFFIX}" for a in payload.get("items", [])), payload)
req = urllib.request.Request(BASE + "/home")
try:
    with opener.open(req) as resp:
        home_status, home_ok = resp.status, b"Today" in resp.read()
except Exception as exc:
    home_status, home_ok = 0, False
check("student home renders", home_status == 200 and home_ok, home_status)

# --- 7. Student blocked from teacher portal ---
status, payload = call("/auth/login", {"email": STUDENT_EMAIL, "password": PASSWORD, "portal": "teacher"})
check("student blocked from teacher portal (403)", status == 403 and payload.get("code") == "TEACHER_ACCOUNT_REQUIRED", (status, payload))

# --- 8. Cleanup test data from the live database (children before parents) ---
conn = sqlite3.connect("backend/data/learncraft.db")
conn.execute("PRAGMA foreign_keys=ON")
for email in (TEACHER_EMAIL, STUDENT_EMAIL):
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        continue
    uid = row[0]
    classes = [r[0] for r in conn.execute("SELECT id FROM teacher_classes WHERE teacher_id = ?", (uid,))]
    for cid in classes:
        targets = [r[0] for r in conn.execute("SELECT id FROM teacher_assignments WHERE class_id = ?", (cid,))]
        for aid in targets:
            conn.execute("DELETE FROM assignment_targets WHERE assignment_id = ?", (aid,))
        conn.execute("DELETE FROM teacher_assignments WHERE class_id = ?", (cid,))
        conn.execute("DELETE FROM teacher_announcements WHERE class_id = ?", (cid,))
        conn.execute("DELETE FROM class_members WHERE class_id = ?", (cid,))
        conn.execute("DELETE FROM student_join_requests WHERE class_id = ?", (cid,))
        conn.execute("DELETE FROM teacher_classes WHERE id = ?", (cid,))
    conn.execute("DELETE FROM student_join_requests WHERE student_id = ? OR teacher_id = ?", (uid, uid))
    conn.execute("DELETE FROM activity_events WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM teacher_notifications WHERE teacher_id = ?", (uid,))
    conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
conn.commit()
conn.close()
print("cleanup done")

print()
failed = [r for r in results if not r[1]]
print(f"TOTAL: {len(results) - len(failed)}/{len(results)} passed")
raise SystemExit(1 if failed else 0)

