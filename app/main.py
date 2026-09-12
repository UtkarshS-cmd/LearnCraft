import json
import os
from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, jsonify, redirect, render_template, request, session

from data.seed import lessons_data as L
from data.seed import mock_data as M
from app.core.security import hash_password, password_policy, verify_password
from app.database.connection import (
    add_student,
    create_user,
    ensure_note_seed,
    get_notes,
    get_user_progress,
    get_student,
    get_user_by_email,
    get_user_by_id,
    get_users,
    initialize_database,
    save_local_progress,
    save_local_submission,
    save_learning_progress,
    update_user_profile,
    upsert_content_item,
    user_payload,
    get_offline_status,
    enqueue_sync_event,
    create_note,
    delete_note,
    set_note_pinned,
    update_note,
)
from app.services.content_catalog import (
    get_lesson as get_academic_lesson,
    first_lesson_for_chapter as get_academic_lesson_for_chapter,
    import_packages,
    list_subjects as list_academic_subjects,
    load_packages,
    subject_detail as get_academic_subject,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "frontend" / "templates"),
    static_folder=str(ROOT_DIR / "frontend" / "static"),
)

from app.api.router import api_bp
from app.api.v1.auth import bp as auth_api_bp
from app.api.v1.ai import bp as ai_api_bp
from app.api.v1.dashboard import bp as dashboard_api_bp
from app.api.v1.lessons import bp as lessons_api_bp
from app.api.v1.progress import bp as progress_api_bp
from app.api.v1.quizzes import bp as quizzes_api_bp
from app.api.v1.subjects import bp as subjects_api_bp
from app.api.v1.users import bp as users_api_bp

for blueprint in (
    api_bp,
    auth_api_bp,
    ai_api_bp,
    dashboard_api_bp,
    lessons_api_bp,
    progress_api_bp,
    quizzes_api_bp,
    subjects_api_bp,
    users_api_bp,
):
    app.register_blueprint(blueprint)
app.config.update(
    SECRET_KEY=os.environ.get("LEARNCRAFT_SECRET_KEY", "dev-secret-key-change-me"),
    SESSION_COOKIE_NAME="learncraft_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

initialize_database()

NETWORK_MODE = os.environ.get("LEARNCRAFT_NETWORK_MODE", "OFFLINE").upper()
MASTER_URL = os.environ.get("LEARNCRAFT_MASTER_URL", "").strip()


def seed_local_content():
    import_packages(load_packages())
    for subject in M.SUBJECTS:
        upsert_content_item(
            f"subject:{subject['slug']}", "subject", subject["name"], subject,
            subject_slug=subject["slug"]
        )
    for lesson_id, lesson in L.LESSONS.items():
        upsert_content_item(
            f"lesson:{lesson_id}", "lesson", lesson["title"], lesson,
            subject_slug=lesson["subject_slug"], asset_path=f"data/content/lessons/{lesson_id}.json"
        )


seed_local_content()


def json_error(message, code, status=400):
    return jsonify({"success": False, "message": message, "code": code}), status


def json_success(message, code, data=None, status=200):
    payload = {"success": True, "message": message, "code": code}
    if data is not None:
        if isinstance(data, dict) and "user" in data:
            payload["user"] = data["user"]
            data = {k: v for k, v in data.items() if k != "user"}
        if data:
            payload["data"] = data
    return jsonify(payload), status


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return user_payload(get_user_by_id(user_id))


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            next_url = request.path
            if request.query_string:
                next_url = f"{next_url}?{request.query_string.decode()}"
            return redirect(f"/login?{urlencode({'next': next_url})}")
        return view(*args, **kwargs)
    return wrapped


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect("/login")
            if user.get("role") not in {r.upper() for r in roles}:
                return json_error("You do not have permission to access this resource.", "FORBIDDEN", 403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def build_student_profile(user=None):
    profile = {"name": "Student", "roll_no": "Student", "avatar": "LC", "level": 1,
               "xp": 0, "streak_days": 0, "overall_progress": 0, "rank": None}
    if user is None:
        return profile
    rows = get_user_progress(user["id"])
    completed = sum(row["status"] == "completed" for row in rows)
    overall = round(sum(row["percent_complete"] for row in rows) / len(rows)) if rows else 0
    profile.update({"name": user.get("name") or "Student", "avatar": (user.get("avatar") or "LC").upper(),
                   "roll_no": user.get("roll_no") or "Student", "xp": completed * 100,
                   "overall_progress": overall, "level": 1 + completed // 5})
    return profile


def student_subjects(user_id):
    rows = get_user_progress(user_id)
    by_subject = {}
    for row in rows:
        by_subject.setdefault(row["subject_slug"], []).append(row["percent_complete"])
    subjects = []
    catalog_subjects = list_academic_subjects()
    for subject in catalog_subjects:
        values = by_subject.get(subject["slug"], [])
        progress_pct = round(sum(values) / len(values)) if values else 0
        subjects.append({**subject, "icon": "◈", "color": "#4F46E5", "bg": "#EEF2FF",
                         "chapters": 0, "progress": progress_pct,
                         "completed": sum(value == 100 for value in values),
                         "tag": "In progress" if progress_pct else "Not started",
                         "current_chapter": "Continue your first lesson" if progress_pct else "Start your first lesson"})
    return subjects


def continue_learning(user_id):
    rows = get_user_progress(user_id)
    if not rows:
        return None
    lesson = L.get_lesson(rows[0]["lesson_id"])
    if not lesson:
        return None
    return {"subject": lesson["subject_name"], "subject_slug": lesson["subject_slug"],
            "subject_color": "#6366F1", "subject_bg": "#EEF2FF", "chapter": lesson["chapter_label"],
            "lesson": lesson["title"], "progress_pct": rows[0]["percent_complete"],
            "time_left": lesson["est"], "last_activity": "Saved on this device",
            "resume_url": f"/subjects/{lesson['subject_slug']}/lessons/{lesson['id']}"}


def shell_ctx(active, user=None):
    return dict(nav=M.NAV, student=build_student_profile(user), active=active, pending_count=0)


@app.route("/")
def index():
    return redirect("/home" if current_user() else "/login")


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/login")
def login_page():
    if current_user():
        return redirect("/home")
    return render_template("login.html", title="Login")


@app.route("/register")
def register_page():
    if current_user():
        return redirect("/home")
    return render_template("login.html", title="Create account")


@app.route("/logout")
def logout_page():
    session.clear()
    return redirect("/login")


@app.post("/auth/register")
def auth_register():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not name or not email or not password:
        return json_error("Name, email, and password are required.", "VALIDATION_ERROR", 400)
    if not email.endswith("@") and "@" not in email:
        return json_error("Please provide a valid email address.", "VALIDATION_ERROR", 400)

    valid, message = password_policy(password)
    if not valid:
        return json_error(message, "VALIDATION_ERROR", 400)

    if get_user_by_email(email):
        return json_error("An account with this email already exists.", "EMAIL_EXISTS", 409)

    password_hash = hash_password(password)
    user = create_user(name=name, email=email, password_hash=password_hash, role="STUDENT")
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True

    return json_success("Account created successfully.", "REGISTERED", {"user": user_payload(user)}, 201)


@app.post("/auth/login")
def auth_login():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not email or not password:
        return json_error("Email and password are required.", "VALIDATION_ERROR", 400)

    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return json_error("Invalid email or password.", "INVALID_CREDENTIALS", 401)

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return json_success("Login successful.", "LOGIN_SUCCESS", {"user": user_payload(user)}, 200)


@app.post("/auth/logout")
def auth_logout():
    session.clear()
    return json_success("Signed out successfully.", "LOGOUT_SUCCESS", None, 200)


@app.get("/auth/me")
def auth_me():
    user = current_user()
    if not user:
        return json_error("Authentication required.", "AUTH_REQUIRED", 401)
    return json_success("User profile loaded.", "USER_LOADED", {"user": user_payload(user)}, 200)


@app.put("/auth/profile")
@require_auth
def auth_update_profile():
    payload = request.get_json(silent=True) or {}
    user = current_user()
    if not user:
        return json_error("Authentication required.", "AUTH_REQUIRED", 401)

    name = payload.get("name")
    email = payload.get("email")
    avatar = payload.get("avatar")
    bio = payload.get("bio")

    if email:
        email = str(email).strip().lower()
        existing = get_user_by_email(email)
        if existing and existing["id"] != user["id"]:
            return json_error("A user with this email already exists.", "EMAIL_EXISTS", 409)

    updated_user = update_user_profile(
        user["id"],
        name=name,
        email=email,
        avatar=avatar,
        bio=bio,
    )
    return json_success("Profile updated.", "PROFILE_UPDATED", {"user": user_payload(updated_user)}, 200)


@app.route("/teacher")
def teacher():
    students = get_users()
    rows = ""
    for student in students:
        rows += f"""
        <tr>
            <td>{student['email']}</td>
            <td>{student['name']}</td>
            <td>🟢 Connected</td>
        </tr>
        """
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Teacher Dashboard</title></head>
    <body>
      <h1>LearnCraft — Teacher Dashboard</h1>
      <h3>Students Registered: {len(students)}</h3>
      <table border="1" cellpadding="10"><tr><th>Email</th><th>Name</th><th>Status</th></tr>{rows}</table>
      <br><a href="/">Student Portal</a>
    </body>
    </html>
    """


@app.route("/home")
@require_auth
def student_home():
    user = current_user()
    ctx = shell_ctx("home", user)
    cont = continue_learning(user["id"])
    return render_template("pages/home.html", title="Home",
                           cont=cont, today_work=[], my_subjects=student_subjects(user["id"]), activity=[],
                           note_count=len(get_notes(user["id"])),
                           pending_assign=0, pending_practicals=0,
                           greeting_sub="Your local learning workspace is ready.",
                           **ctx)


@app.route("/my-learning")
@require_auth
def my_learning():
    return render_template("pages/my_learning.html", title="My Learning",
                           items=M.MY_LEARNING, cont=M.CONTINUE_LEARNING,
                           lesson_map=L.FIRST_LESSON, **shell_ctx("my-learning", current_user()))


@app.route("/subjects")
@require_auth
def subjects():
    return render_template("pages/subjects.html", title="Subjects",
                           subjects=student_subjects(current_user()["id"]), **shell_ctx("subjects", current_user()))


@app.route("/subjects/<slug>")
@require_auth
def subject_detail(slug):
    catalog = get_academic_subject(slug)
    if catalog:
        subject = catalog["subject"]
        chapters = catalog["chapters"]
        page = {
            "slug": slug, "name": subject["name"], "description": subject["description"],
            "icon": "◈", "color": "#4F46E5", "bg": "#EEF2FF", "tags": ["CBSE Class X", subject["academic_year"]],
            "progress": 0, "continue": {"href": f"/subjects/{slug}", "cta": "Start learning",
            "chapter_label": "Choose a chapter", "lesson": "Your next lesson", "time_left": "Offline-ready", "progress": 0},
            "units": [{"id": "content", "title": "Chapters", "desc": "Learn the concepts in curriculum order.",
                       "chapters": [{"n": c["chapter_number"], "title": c["title"], "est": "Lessons available",
                                     "lessons_count": 1, "status": "Available", "progress": 0,
                                     "is_current": False, "is_next": c["chapter_number"] == chapters[0]["chapter_number"],
                                     "prereq": "", "sim": "Practice", "practical": "Notes", "quiz": "Test"} for c in chapters]}],
            "practice": [], "sims": [], "practicals": []
        }
        first = None
        for chapter in chapters:
            detail = get_academic_lesson_for_chapter(chapter["chapter_id"])
            if detail:
                first = detail["lesson_id"]
                page["continue"]["href"] = f"/subjects/{slug}/lessons/{first}"
                page["continue"]["chapter_label"] = f"Chapter {chapter['chapter_number']} · {chapter['title']}"
                page["continue"]["lesson"] = detail["title"]
                break
        return render_template("pages/subject_detail.html", title=subject["name"], page=page,
                               first_lesson=first, **shell_ctx("subjects", current_user()))
    page = M.get_subject_page(slug)
    if page is None:
        return redirect("/subjects")
    page = dict(page)
    first = L.FIRST_LESSON.get(slug)
    if first:
        page["continue"] = dict(page["continue"], href=f"/subjects/{slug}/lessons/{first}")
    return render_template("pages/subject_detail.html", title=page["name"],
                           page=page, first_lesson=first, **shell_ctx("subjects", current_user()))


@app.route("/subjects/<slug>/lessons/<lesson_id>")
@require_auth
def lesson_player(slug, lesson_id):
    lesson = get_academic_lesson(lesson_id) or L.get_lesson(lesson_id)
    if lesson is None or lesson["subject_slug"] != slug:
        return redirect(f"/subjects/{slug}")
    seen, stages = set(), []
    for block in lesson["blocks"]:
        if block["stage"] not in seen:
            seen.add(block["stage"])
            stages.append(block["stage"])
    return render_template("pages/lesson.html", title=lesson["title"],
                           lesson=lesson, stages=stages, **shell_ctx("subjects", current_user()))


@app.route("/practical")
@require_auth
def practical():
    return render_template("pages/practical.html", title="Practical",
                           practicals=M.PRACTICALS, workspace=M.PRACTICAL_WORKSPACE,
                           **shell_ctx("practical", current_user()))


@app.route("/assignments")
@require_auth
def assignments():
    pending = sum(1 for a in M.ASSIGNMENTS if a["status"] != "Submitted")
    return render_template("pages/assignments.html", title="Assignments",
                           assignments=M.ASSIGNMENTS, assignment=M.ASSIGNMENT_WORKSPACE,
                           assignment_types=M.ASSIGNMENT_TYPES, pending=pending,
                           **shell_ctx("assignments", current_user()))


@app.route("/sandbox")
@require_auth
def sandbox():
    return render_template("pages/sandbox.html", title="Sandbox",
                           cards=M.SANDBOX_CARDS, **shell_ctx("sandbox", current_user()))


@app.route("/progress")
@require_auth
def progress():
    return render_template("pages/progress.html", title="Progress",
                           subjects=M.SUBJECTS, weekly=M.WEEKLY,
                           progress_subjects=M.PROGRESS_SUBJECTS,
                           next_action=M.PROGRESS_NEXT, pending_work=M.PROGRESS_PENDING,
                           activity_history=M.PROGRESS_ACTIVITY,
                           achievements=M.ACHIEVEMENTS, **shell_ctx("progress", current_user()))


@app.route("/notes")
@require_auth
def notes():
    user = current_user()
    search = request.args.get("q", "").strip()
    subject = request.args.get("subject", "").strip()
    return render_template("pages/notes.html", title="Notes",
                           subjects=M.SUBJECTS, notes=get_notes(user["id"], search, subject),
                           search=search, selected_subject=subject,
                           context={"subject": request.args.get("context_subject", ""),
                                    "chapter": request.args.get("context_chapter", ""),
                                    "source_type": request.args.get("source_type", ""),
                                    "source_id": request.args.get("source_id", ""),
                                    "source_title": request.args.get("source_title", "")},
                           **shell_ctx("notes", current_user()))


@app.post("/api/notes")
@require_auth
def api_create_note():
    user = current_user()
    payload = request.get_json(silent=True) or {}
    title, body, subject = (str(payload.get(key, "")).strip() for key in ("title", "body", "subject"))
    if not title or not subject:
        return json_error("Title and subject are required.", "VALIDATION_ERROR", 400)
    return jsonify(create_note(user["id"], title, body, subject, payload.get("chapter"),
                               payload.get("source_type"), payload.get("source_id"),
                               payload.get("source_title"))), 201


@app.put("/api/notes/<client_id>")
@require_auth
def api_update_note(client_id):
    user = current_user()
    payload = request.get_json(silent=True) or {}
    title, body, subject = (str(payload.get(key, "")).strip() for key in ("title", "body", "subject"))
    if not title or not subject:
        return json_error("Title and subject are required.", "VALIDATION_ERROR", 400)
    note = update_note(user["id"], client_id, title, body, subject, payload.get("chapter"))
    return jsonify(note) if note else json_error("Note not found.", "NOT_FOUND", 404)


@app.post("/api/notes/<client_id>/pin")
@require_auth
def api_pin_note(client_id):
    user = current_user()
    payload = request.get_json(silent=True) or {}
    note = set_note_pinned(user["id"], client_id, bool(payload.get("pinned")))
    return jsonify(note) if note else json_error("Note not found.", "NOT_FOUND", 404)


@app.delete("/api/notes/<client_id>")
@require_auth
def api_delete_note(client_id):
    delete_note(current_user()["id"], client_id)
    return json_success("Note deleted.", "NOTE_DELETED", None, 200)


@app.get("/api/system/status")
def api_system_status():
    return jsonify({
        "mode": NETWORK_MODE if NETWORK_MODE in {"OFFLINE", "LOCAL_NETWORK", "INTERNET"} else "OFFLINE",
        "internet_enabled": False,
        "master_configured": bool(MASTER_URL),
        "core_storage": "sqlite",
        "asset_storage": "local-filesystem",
        **get_offline_status(),
    })


@app.post("/api/local/state")
@require_auth
def api_local_state():
    payload = request.get_json(silent=True) or {}
    kind = payload.get("kind", "progress")
    record_id = str(payload.get("record_id", "")).strip()
    record = payload.get("payload", {})
    status = payload.get("status", "local")
    if not record_id or kind not in {"progress", "submission"}:
        return json_error("A valid local record is required.", "VALIDATION_ERROR", 400)
    if kind == "submission":
        save_local_submission(record_id, record_id, record, status=status)
    else:
        save_local_progress(record_id, record, sync_status="local")
    if status in {"SUBMITTED", "submitted", "completed"} or kind == "submission":
        enqueue_sync_event(kind, record_id, "upsert", record)
    return json_success("Local state saved.", "LOCAL_STATE_SAVED", {"storage": "sqlite", "sync_status": "queued" if kind == "submission" else "local"}, 200)


@app.get("/api/content/catalog")
@require_auth
def api_content_catalog():
    from app.database.connection import get_connection
    connection = get_connection()
    rows = connection.execute(
        "SELECT content_id, kind, subject_slug, title, payload_json, asset_path, content_version, source FROM content_items ORDER BY kind, title"
    ).fetchall()
    connection.close()
    return jsonify([{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows])


@app.get("/api/sync/queue")
@require_auth
def api_sync_queue():
    from app.database.connection import get_connection
    connection = get_connection()
    rows = connection.execute(
        "SELECT event_id, entity_type, entity_id, operation, payload_json, status, created_at FROM sync_queue WHERE status = 'queued' ORDER BY id"
    ).fetchall()
    connection.close()
    return jsonify([{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows])


@app.route("/profile")
@require_auth
def profile():
    user = current_user()
    return render_template("pages/profile.html", title="Profile", cont=continue_learning(user["id"]),
                           **shell_ctx("profile", user))


@app.route("/settings")
@require_auth
def settings():
    return render_template("pages/settings.html", title="Settings", **shell_ctx("settings", current_user()))


@app.route("/help")
@require_auth
def help_page():
    return render_template("pages/help.html", title="Help", **shell_ctx("help", current_user()))


@app.route("/tests")
@require_auth
def tests_page():
    return render_template("pages/tests.html", title="Tests", **shell_ctx("tests", current_user()))


@app.route("/ask-ai")
@require_auth
def ask_ai():
    lesson_id = request.args.get("lesson_id", "")
    lesson = get_academic_lesson(lesson_id) if lesson_id else None
    return render_template("pages/ask_ai.html", title="Ask AI", lesson=lesson,
                           **shell_ctx("ask-ai", current_user()))


if __name__ == "__main__":
    print("--------------------------------")
    print(" LearnCraft Local Server")
    print("--------------------------------")
    print("Server starting...")
    app.run(host="0.0.0.0", port=5000, debug=True)


def create_app():
    return app
