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
from app.services.auth_service import AuthService, EmailExistsError
from app.services.password_reset import PasswordResetService
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
    list_subject_lessons as get_subject_lessons,
    list_subject_questions as get_subject_questions,
    list_subjects as list_academic_subjects,
    list_class9_subjects,
    list_class10_subjects,
    load_packages,
    class10_lesson,
    class10_subject,
    class9_lesson,
    class9_subject,
    load_feature_simulations,
    simulation_covers_chapter,
    simulations_for_subject,
    subject_detail as get_academic_subject,
)
from app.services.teacher_control import access_allowed, record_event, student_announcements, student_assignments, teacher_classes

ROOT_DIR = Path(__file__).resolve().parents[2]
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
from app.api.v1.curriculum import bp as curriculum_api_bp
from app.api.v1.users import bp as users_api_bp
from app.api.v1.teacher import bp as teacher_api_bp

for blueprint in (
    api_bp,
    auth_api_bp,
    ai_api_bp,
    dashboard_api_bp,
    lessons_api_bp,
    progress_api_bp,
    quizzes_api_bp,
    subjects_api_bp,
    curriculum_api_bp,
    users_api_bp,
    teacher_api_bp,
):
    app.register_blueprint(blueprint)
_secret = os.environ.get("LEARNCRAFT_SECRET_KEY")
if not _secret:
    import sys
    _mode = os.environ.get("LEARNCRAFT_NETWORK_MODE", "OFFLINE").upper()
    _testing = os.environ.get("FLASK_TESTING") or os.environ.get("PYTEST_CURRENT_TEST")
    if _mode == "OFFLINE" and _testing:
        _secret = "test-secret-do-not-use-in-production"
    else:
        sys.stderr.write("FATAL: LEARNCRAFT_SECRET_KEY must be set for this deployment.\n")
        sys.exit(1)
app.config.update(
    SECRET_KEY=_secret,
    SESSION_COOKIE_NAME="learncraft_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAIL_HOST=os.environ.get("LEARNCRAFT_MAIL_HOST"),
    MAIL_PORT=int(os.environ.get("LEARNCRAFT_MAIL_PORT", "587")),
    MAIL_USERNAME=os.environ.get("LEARNCRAFT_MAIL_USERNAME"),
    MAIL_PASSWORD=os.environ.get("LEARNCRAFT_MAIL_PASSWORD"),
    MAIL_FROM=os.environ.get("LEARNCRAFT_MAIL_FROM", "no-reply@learncraft.local"),
    MAIL_USE_TLS=os.environ.get("LEARNCRAFT_MAIL_USE_TLS", "true").lower() == "true",
)

password_reset_service = PasswordResetService()
auth_service = AuthService()

_RUNTIME_READY = False

NETWORK_MODE = os.environ.get("LEARNCRAFT_NETWORK_MODE", "OFFLINE").upper()
MASTER_URL = os.environ.get("LEARNCRAFT_MASTER_URL", "").strip()


def seed_local_content():
    try:
        import_packages(load_packages())
    except Exception:
        # Curriculum seeding must never break app startup (fresh checkout,
        # read-only FS, partial data). Tests seed explicitly.
        pass
    for subject in M.SUBJECTS:
        try:
            upsert_content_item(
                f"subject:{subject['slug']}", "subject", subject["name"], subject,
                subject_slug=subject["slug"]
            )
        except Exception:
            continue
    for lesson_id, lesson in L.LESSONS.items():
        try:
            upsert_content_item(
                f"lesson:{lesson_id}", "lesson", lesson["title"], lesson,
                subject_slug=lesson["subject_slug"], asset_path=f"data/content/lessons/{lesson_id}.json"
            )
        except Exception:
            continue


try:
    initialize_database()
    seed_local_content()
    _RUNTIME_READY = True
except Exception:
    # Import-time DB access must never crash test collection on read-only FS.
    pass


@app.before_request
def _lazy_runtime_bootstrap():
    global _RUNTIME_READY
    if not _RUNTIME_READY:
        try:
            initialize_database()
            seed_local_content()
            _RUNTIME_READY = True
        except Exception:
            pass


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


def is_teacher_user(user=None):
    return bool(user) and user.get("role") in {"TEACHER", "ADMIN"}


def landing_for(user=None):
    return "/teacher" if is_teacher_user(user) else "/home"


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            if request.path.startswith("/api/"):
                return json_error("Authentication required.", "UNAUTHORIZED", 401)
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
        if not row.get("subject_slug"):
            continue
        by_subject.setdefault(row["subject_slug"], []).append(int(row.get("percent_complete", 0) or 0))
    subjects = []
    catalog_subjects = list_academic_subjects()
    for subject in catalog_subjects:
        values = by_subject.get(subject["slug"], [])
        progress_pct = round(sum(values) / len(values)) if values else 0
        current_chapter = "Start your first lesson" if not values else (
            "Continue your next lesson" if progress_pct < 100 else "Topic complete"
        )
        subjects.append({**subject, "icon": "◈", "color": "#4F46E5", "bg": "#EEF2FF",
                         "chapters": 0, "progress": progress_pct,
                         "completed": sum(value == 100 for value in values),
                         "tag": "In progress" if progress_pct else "Not started",
                         "current_chapter": current_chapter})
    for subject in list_class9_subjects():
        subjects.append({
            "slug": subject["slug"], "name": subject["name"], "description": subject["description"],
            "icon": "◈", "color": "#0F766E", "bg": "#ECFDF5", "chapters": len(subject["chapters"]),
            "progress": 0, "completed": 0, "tag": "Not started", "current_chapter": "Start your first lesson",
        })
    for subject in list_class10_subjects():
        subjects.append({
            "slug": subject["slug"], "name": subject["name"], "description": subject["description"],
            "icon": "◈", "color": "#B45309", "bg": "#FFFBEB", "chapters": len(subject["chapters"]),
            "progress": 0, "completed": 0, "tag": "Not started", "current_chapter": "Start your first lesson",
        })
    return subjects


def build_user_progress_dashboard(user_id):
    rows = sorted(get_user_progress(user_id), key=lambda row: (int(row.get("percent_complete", 0) or 0), row.get("updated_at") or ""))
    subject_cards = student_subjects(user_id)
    next_row = None
    for row in rows:
        if int(row.get("percent_complete", 0) or 0) < 100:
            next_row = row
            break
    next_action = {
        "title": "Start learning",
        "detail": "Your profile has no lesson progress yet.",
        "reason": "Choose any subject to begin your first chapter.",
        "href": "/subjects",
        "action": "Browse subjects"
    }
    if next_row:
        subject = next_row.get("subject_slug") or "subjects"
        detail = next_row.get("last_activity") or f"{next_row.get('percent_complete', 0)}% complete"
        next_action = {
            "title": f"{subject.replace('-', ' ').title()} progress",
            "detail": f"{detail} · next learning checkpoint",
            "reason": "This is your current learning progress from your profile data.",
            "href": f"/subjects/{subject}",
            "action": "Continue"
        }
    pending_work = []
    for row in rows[:5]:
        if int(row.get("percent_complete", 0) or 0) >= 100:
            continue
        title = row.get("lesson_id") or row.get("subject_slug") or "Learning task"
        pending_work.append({
            "kind": "Lesson" if row.get("lesson_id") else "Module",
            "title": title.replace("-", " ").title(),
            "detail": f"{row.get('percent_complete', 0)}% complete · {row.get('last_activity') or 'recent activity'}",
            "href": "/my-learning",
            "action": "Resume"
        })
    activity_history = []
    for row in rows[:4]:
        pct = int(row.get("percent_complete", 0) or 0)
        activity_history.append({
            "title": row.get("subject_slug") or "Learning activity",
            "detail": f"{pct}% complete · {row.get('last_activity') or 'Saved locally'}",
            "time": row.get("updated_at") or "Recently",
            "tone": "ok" if pct >= 80 else "info"
        })
    achievements = [
        {"name": "First step", "desc": "Started learning", "icon": "★", "earned": any(int(row.get("percent_complete", 0) or 0) > 0 for row in rows)},
        {"name": "Momentum", "desc": "50%+ progress", "icon": "⚡", "earned": any(int(row.get("percent_complete", 0) or 0) >= 50 for row in rows)},
        {"name": "Chapter done", "desc": "100% complete", "icon": "✓", "earned": any(int(row.get("percent_complete", 0) or 0) >= 100 for row in rows)},
    ]
    return {
        "subjects": subject_cards,
        "next_action": next_action,
        "pending_work": pending_work or [{"kind": "Profile", "title": "No active tasks", "detail": "Fresh profile — start the first subject.", "href": "/subjects", "action": "Open subjects"}],
        "activity_history": activity_history or [{"title": "Fresh start", "detail": "No learning activity yet", "time": "Just now", "tone": "muted"}],
        "achievements": achievements,
    }


def continue_learning(user_id):
    rows = get_user_progress(user_id)
    if not rows:
        return None
    # Resume the most recently active incomplete lesson; completed rows sort last.
    def _sort_key(row):
        pct = int(row.get("percent_complete", 0) or 0)
        return (pct >= 100, -(pct or 0), str(row.get("updated_at") or "")[::-1])
    row = sorted(rows, key=_sort_key)[0]
    lesson = L.get_lesson(row.get("lesson_id")) if row.get("lesson_id") else None
    if not lesson:
        subject = next((subject for subject in list_academic_subjects() if subject["slug"] == row.get("subject_slug")), None)
        subject_slug = row.get("subject_slug") or "subjects"
        subject_name = subject["name"] if subject else subject_slug.replace('-', ' ').title()
        return {
            "subject": subject_name,
            "subject_slug": subject_slug,
            "subject_color": "#6366F1",
            "subject_bg": "#EEF2FF",
            "chapter": "Current progress",
            "lesson": "Continue learning",
            "progress_pct": int(row.get("percent_complete", 0) or 0),
            "time_left": "Based on profile data",
            "last_activity": row.get("last_activity") or "Saved on this device",
            "resume_url": f"/subjects/{subject_slug}"
        }
    return {"subject": lesson["subject_name"], "subject_slug": lesson["subject_slug"],
            "subject_color": "#6366F1", "subject_bg": "#EEF2FF", "chapter": lesson["chapter_label"],
            "lesson": lesson["title"], "progress_pct": int(row.get("percent_complete", 0) or 0),
            "time_left": lesson["est"], "last_activity": row.get("last_activity") or "Saved on this device",
            "resume_url": f"/subjects/{lesson['subject_slug']}/lessons/{lesson['id']}"}


def shell_ctx(active, user=None):
    pending = 0
    if user and user.get("role") == "STUDENT":
        try:
            pending = len(student_assignments(user["id"]))
        except Exception:
            pending = 0
    return dict(nav=M.NAV, student=build_student_profile(user), active=active, pending_count=pending,
                is_teacher=is_teacher_user(user))


def live_today_work(user_id):
    """Live teacher-sent work for the student home 'Today's work' rail."""
    items = []
    try:
        assignments = student_assignments(user_id)
    except Exception:
        assignments = []
    try:
        announcements = student_announcements(user_id)
    except Exception:
        announcements = []
    for item in (assignments or [])[:5]:
        meta = str(item.get("resource_type") or "activity")
        if item.get("resource_id"):
            meta = f"{meta} · {item.get('resource_id')}"
        items.append({
            "kind": "Assignment",
            "title": item.get("title") or "Assignment from your teacher",
            "due": item.get("due_at") or "No due date",
            "meta": meta,
            "href": "/assignments#from-teacher",
            "action": "Open",
            "urgent": bool(item.get("due_at")),
        })
    for note in (announcements or [])[:3]:
        message = str(note.get("message") or "Announcement")
        items.append({
            "kind": "Announcement",
            "title": message[:90],
            "due": note.get("created_at") or "",
            "meta": "From your teacher",
            "href": "/assignments#from-teacher",
            "action": "View",
            "urgent": False,
        })
    return items, len(assignments or [])


@app.route("/")
def index():
    user = current_user()
    if not user:
        return redirect("/login")
    return redirect(landing_for(user))


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/login")
def login_page():
    user = current_user()
    if user:
        return redirect(landing_for(user))
    return render_template("login.html", title="Login")


@app.route("/register")
def register_page():
    user = current_user()
    if user:
        return redirect(landing_for(user))
    return render_template("login.html", title="Create account")


@app.route("/logout")
def logout_page():
    user = current_user()
    if user:
        record_event(user["id"], "USER_LOGOUT", detail=f"{user['name']} signed out")
    session.clear()
    return redirect("/login")


@app.route("/offline")
def offline_page():
    return render_template("offline.html", title="Offline mode")


@app.route("/service-worker.js")
def service_worker():
    sw_path = ROOT_DIR / "frontend" / "static" / "js" / "service-worker.js"
    content = sw_path.read_text(encoding="utf-8")
    response = app.response_class(content, mimetype="application/javascript; charset=utf-8")
    response.headers["Service-Worker-Allowed"] = "/"
    return response



@app.post("/auth/register")
def auth_register():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    account_type = str(payload.get("account_type", "student")).strip().lower()

    if not name or not email or not password:
        return json_error("Name, email, and password are required.", "VALIDATION_ERROR", 400)
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return json_error("Please provide a valid email address.", "VALIDATION_ERROR", 400)
    if account_type not in {"student", "teacher"}:
        return json_error("Invalid account type.", "VALIDATION_ERROR", 400)

    try:
        # Canonical registration: /auth/* and /api/v1/auth/* share this service,
        # so the same requested account type always yields the same role.
        user = auth_service.create_user(name=name, email=email, password=password, account_type=account_type)
    except EmailExistsError:
        return json_error("An account with this email already exists.", "EMAIL_EXISTS", 409)
    except ValueError as exc:
        return json_error(str(exc), "VALIDATION_ERROR", 400)

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

    user = auth_service.authenticate(email, password)
    if not user:
        return json_error(
            "Invalid email or password. You can reset it from the Forgot password link.",
            "INVALID_CREDENTIALS",
            401,
        )
    portal = str(payload.get("portal", "student")).strip().lower()
    if not auth_service.validate_portal(user, portal):
        return json_error("This account is not a teacher account.", "TEACHER_ACCOUNT_REQUIRED", 403)

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    record_event(user["id"], "USER_LOGIN", detail=f"{user['name']} signed in")
    return json_success("Login successful.", "LOGIN_SUCCESS", {"user": user_payload(user)}, 200)


@app.post("/auth/password-reset/request")
def request_password_reset():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    if not email:
        return json_error("Email is required.", "VALIDATION_ERROR", 400)

    # Offline-first: never reveal whether the account exists and never fail
    # when SMTP is unconfigured. OTP email is best-effort only.
    try:
        password_reset_service.request_otp(email)
    except Exception:
        pass
    return json_success("If an account exists, password reset instructions are ready. You can set a new password directly below.", "OTP_SENT")


@app.post("/auth/password-reset/confirm")
def confirm_password_reset():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    otp = str(payload.get("otp", "")).strip()
    new_password = str(payload.get("new_password", ""))
    if not email or not otp or not new_password:
        return json_error("Email, OTP, and new password are required.", "VALIDATION_ERROR", 400)

    if not otp.isdigit() or len(otp) != 6:
        return json_error("A valid 6-digit OTP is required.", "INVALID_OTP", 400)

    success, message = password_reset_service.reset_password(email, otp, new_password)
    if not success:
        code = "VALIDATION_ERROR" if message.startswith("Password must") else "INVALID_OTP"
        return json_error(message, code, 400)
    return json_success(message, "PASSWORD_RESET")


@app.post("/auth/logout")
def auth_logout():
    user = current_user()
    if user:
        record_event(user["id"], "USER_LOGOUT", detail=f"{user['name']} signed out")
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
@require_roles("TEACHER", "ADMIN")
def teacher():
    user = current_user()
    try:
        existing_classes = teacher_classes(user["id"])
    except Exception:
        existing_classes = []
    is_fresh = len(existing_classes) == 0
    show_onboarding = is_fresh or request.args.get("fresh") == "1"
    return render_template(
        "teacher_dashboard.html",
        title="Teacher Control Center",
        user=user,
        is_fresh=is_fresh,
        show_onboarding=show_onboarding,
    )


@app.route("/home")
@require_auth
def student_home():
    user = current_user()
    # Teachers get their own fresh Control Center instead of the student home.
    if is_teacher_user(user):
        return redirect("/teacher")
    today_work, pending_assign = live_today_work(user["id"])
    ctx = shell_ctx("home", user)
    cont = continue_learning(user["id"])
    return render_template("pages/home.html", title="Home",
                           cont=cont, today_work=today_work, my_subjects=student_subjects(user["id"]), activity=[],
                           note_count=len(get_notes(user["id"])),
                           pending_assign=pending_assign, pending_practicals=0,
                           greeting_sub="Your local learning workspace is ready.",
                           **ctx)


@app.route("/my-learning")
@require_auth
def my_learning():
    user = current_user()
    return render_template("pages/my_learning.html", title="My Learning",
                           my_subjects=student_subjects(user["id"]),
                           cont=continue_learning(user["id"]),
                           **shell_ctx("my-learning", user))


@app.route("/subjects")
@require_auth
def subjects():
    return render_template("pages/subjects.html", title="Subjects",
                           subjects=student_subjects(current_user()["id"]), **shell_ctx("subjects", current_user()))


@app.route("/subjects/<slug>")
@require_auth
def subject_detail(slug):
    user = current_user()
    if user and user.get("role") == "STUDENT" and not access_allowed(user["id"], "subject", slug):
        return "This subject is currently unavailable.", 403
    feature = class9_subject(slug) or class10_subject(slug)
    if feature:
        chapters = feature["chapters"]
        is_class10 = class10_subject(slug) is not None
        build_lesson = class10_lesson if is_class10 else class9_lesson
        feature_sims = simulations_for_subject(slug)
        first = build_lesson(slug, chapters[0]["number"])
        class_label = "X" if is_class10 else "IX"
        color, bg = ("#B45309", "#FFFBEB") if is_class10 else ("#0F766E", "#ECFDF5")
        page = {
            "slug": slug, "name": feature["name"], "description": feature["description"],
            "icon": "◈", "color": color, "bg": bg,
            "tags": [f"CBSE Class {class_label}", "2026-27", "NCERT aligned"], "pdf_url": feature["pdf_url"], "progress": 0,
            "continue": {"href": f"/subjects/{slug}/lessons/{first['lesson_id']}", "cta": "Start learning",
                          "chapter_label": f"Chapter {chapters[0]['number']} · {chapters[0]['title']}",
                          "lesson": first["title"], "time_left": first["est"], "progress": 0},
            "units": [{"id": "u1", "title": "CBSE Class IX chapters", "desc": "Learn, practise and review in NCERT chapter order.", "chapters": []}],
            "practice": [], "sims": [], "practicals": [], "assignments": [], "notes": [], "references": []
        }
        for chapter in chapters:
            lesson = build_lesson(slug, chapter["number"])
            chapter_sims = [sim for sim in feature_sims if simulation_covers_chapter(sim, slug, chapter["number"])]
            page["units"][0]["chapters"].append({
                "n": chapter["number"], "title": chapter["title"], "est": "20 min",
                "lessons_count": 1, "status": "Available", "progress": 0,
                "is_current": chapter["number"] == 1, "is_next": chapter["number"] == 1,
                "prereq": "", "sim": chapter_sims[0]["name"] if chapter_sims else "Concept sandbox", "practical": "Guided activity", "quiz": "1 MCQ",
            })
            page["practice"].append({
                "title": f"Chapter {chapter['number']} MCQ · {chapter['title']}",
                "meta": "Original concept check · 1 question", "status": "Available",
                "prompt": f"Which topic is the focus of Chapter {chapter['number']}?",
                "answer": chapter["title"],
            })
            for sim in chapter_sims:
                page["sims"].append({"title": f"Chapter {chapter['number']} · {sim['name']}", "description": sim["description"], "href": f"/student/simulation/{sim['id']}", "software_type": sim["software_type"]})
            page["practicals"].append({"title": f"{chapter['title']} activity", "env": "Offline guided practical", "steps": "3 steps", "due": "Self paced", "status": "Available"})
            page["assignments"].append({"title": f"{chapter['title']} review sheet", "meta": "Notes + 5-minute recall", "due": "Self paced", "status": "Not started"})
            page["notes"].append({"title": f"{chapter['title']} study note", "body": chapter["summary"], "updated": "Curriculum seed"})
            for sim in chapter_sims:
                page["notes"].extend({"title": f"{chapter['title']} · Lab note", "body": note, "updated": "Simulation guide"} for note in sim["notes"])
                page["references"].extend({"title": ref["title"], "url": ref["url"], "chapter": chapter["title"]} for ref in sim["references"])
                page["practice"].extend({"title": f"{chapter['title']} practice set", "meta": "Offline simulation reflection", "status": "Available", "prompt": prompt} for prompt in sim["practice_set"])
        return render_template("pages/subject_detail.html", title=feature["name"], page=page,
                               first_lesson=first["lesson_id"], **shell_ctx("subjects", current_user()))
    catalog = get_academic_subject(slug)
    if catalog:
        subject = catalog["subject"]
        chapters = catalog["chapters"]
        user = current_user()
        lessons = get_subject_lessons(slug)
        questions = get_subject_questions(slug)

        lessons_by_chapter = {}
        for lesson in lessons:
            lessons_by_chapter.setdefault(lesson["chapter_id"], []).append(lesson)

        question_counts = {}
        for q in questions:
            question_counts[q["chapter_id"]] = question_counts.get(q["chapter_id"], 0) + 1

        chapter_entries, first = [], None
        for index, chapter in enumerate(chapters):
            chapter_lessons = lessons_by_chapter.get(chapter["chapter_id"], [])
            first_lesson = (chapter_lessons[0] if chapter_lessons
                            else get_academic_lesson_for_chapter(chapter["chapter_id"]))
            first_url = f"/subjects/{slug}/lessons/{first_lesson['lesson_id']}" if first_lesson else None
            if first is None and first_url:
                first = first_lesson["lesson_id"]
            total_minutes = sum((l.get("estimated_minutes") or 0) for l in chapter_lessons)
            chapter_entries.append({
                "n": chapter["chapter_number"],
                "title": chapter["title"],
                "summary": chapter["summary"],
                "est": f"{total_minutes} min of lessons" if total_minutes else "Lessons available",
                "lessons_count": len(chapter_lessons),
                "status": "In Progress" if (index == 0 and chapter_lessons) else (
                    "Available" if chapter_lessons else "Locked"),
                "progress": 0,
                "is_current": index == 0 and bool(chapter_lessons),
                "is_next": index == 1 and bool(chapter_lessons),
                "prereq": "",
                "sim": "Sandbox", "practical": "Lab notes", "quiz": "Test",
                "start_url": first_url or "/sandbox",
                "lessons": [{
                    "lesson_id": l["lesson_id"],
                    "title": l["title"],
                    "summary": l.get("summary", ""),
                    "url": f"/subjects/{slug}/lessons/{l['lesson_id']}",
                    "est": f"{l['estimated_minutes']} min",
                } for l in chapter_lessons],
            })

        practice = [{
            "title": f"{c['title']} — Question bank",
            "meta": f"{question_counts.get(c['chapter_id'], 0)} questions · MCQs + short answer",
            "status": "Available" if question_counts.get(c["chapter_id"]) else "Locked",
        } for c in chapters]
        sims = [f"{c['title']} simulator" for c in chapters]
        practicals = [{
            "title": f"{c['title']} lab",
            "env": "Local lab workspace", "steps": f"{len(lessons_by_chapter.get(c['chapter_id'], []))} activities",
            "due": "Self-paced", "status": "Available" if lessons_by_chapter.get(c["chapter_id"]) else "Locked",
        } for c in chapters]
        assignments = [{
            "title": f"{c['title']} — NCERT exercises",
            "meta": f"{question_counts.get(c['chapter_id'], 0)} questions",
            "due": "Self-paced", "status": "Available" if question_counts.get(c["chapter_id"]) else "Locked",
        } for c in chapters]
        notes = [{"title": f"Revision — {c['title']}", "body": c["summary"],
                  "updated": "Seeded · offline"} for c in chapters]

        continue_lesson = next((entry for entry in chapter_entries if entry["lessons_count"]), chapter_entries[0] if chapter_entries else None)
        continue_url = continue_lesson["start_url"] if continue_lesson and continue_lesson["start_url"] else f"/subjects/{slug}"
        continue_title = (continue_lesson["lessons"][0]["title"] if continue_lesson and continue_lesson["lessons"] else "Your next lesson")

        page = {
            "slug": slug, "name": subject["name"], "description": subject["description"],
            "icon": "◈", "color": "#4F46E5", "bg": "#EEF2FF",
            "tags": ["CBSE Class X", subject["academic_year"]],
            "progress": 0,
            "continue": {
                "href": continue_url, "cta": "Start learning",
                "chapter_label": (f"Chapter {continue_lesson['n']} · {continue_lesson['title']}"
                                  if continue_lesson else "Choose a chapter"),
                "lesson": continue_title, "time_left": "Offline-ready", "progress": 0,
            },
            "units": [{"id": "u2", "title": "Chapters", "desc": "Learn the concepts in curriculum order.",
                       "chapters": chapter_entries}],
            "practice": practice, "sims": sims, "practicals": practicals,
            "assignments": assignments, "notes": notes,
        }
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
    user = current_user()
    if user and user.get("role") == "STUDENT" and not access_allowed(user["id"], "lesson", lesson_id):
        return "This lesson is currently unavailable.", 403
    lesson = get_academic_lesson(lesson_id) or L.get_lesson(lesson_id)
    if lesson is None and (class9_subject(slug) or class10_subject(slug)):
        prefix = f"{slug}-ch"
        if lesson_id.startswith(prefix) and lesson_id.endswith("-overview"):
            try:
                chapter_number = int(lesson_id[len(prefix):-len("-overview")])
            except (ValueError, TypeError):
                return redirect(f"/subjects/{slug}")
            lesson = class10_lesson(slug, chapter_number) if class10_subject(slug) else class9_lesson(slug, chapter_number)
    if lesson is None or lesson.get("subject_slug") != slug:
        return redirect(f"/subjects/{slug}")
    # Collect the ordered stage rail. Blocks are normalized upstream, but stay
    # defensive so a legacy/hand-edited lesson can never crash the player.
    seen, stages = set(), []
    for block in lesson.get("blocks") or []:
        stage = str(block.get("stage") or "CONCEPT").upper()
        if stage not in seen:
            seen.add(stage)
            stages.append(stage)
    if not stages:
        stages = ["CONCEPT"]
    return render_template("pages/lesson.html", title=lesson["title"],
                           lesson=lesson, stages=stages, **shell_ctx("subjects", current_user()))


@app.route("/practical")
@require_auth
def practical():
    user = current_user()
    subjects = student_subjects(user["id"])
    subject = next((item for item in subjects if item["progress"] > 0), subjects[0]) if subjects else {
        "name": "Practice",
        "slug": "physics",
        "bg": "#FFF7ED",
        "color": "#EA580C",
        "progress": 0,
        "current_chapter": "Start your first practical"
    }
    workspace = {
        "subject": subject["name"],
        "subject_bg": subject["bg"],
        "subject_color": subject["color"],
        "title": f"{subject['name']} Practical Lab",
        "environment": "Local lab workspace",
        "step": f"{subject['progress']}% complete",
        "progress": subject["progress"],
        "time": "Based on profile progress",
        "mode": "code",
        "instructions": "Complete the practical exercise for your current subject progress. This value updates from your real learning data.",
        "requirements": ["Review current progress", "Work in the lab", "Save your result"],
        "starter_code": "# Write your code here\nprint(\"Practice started\")\n",
        "tests": [
            {"id": "p1", "name": "Progress check", "detail": "Ensures the lab is aligned with your current profile progress."},
            {"id": "p2", "name": "Completion check", "detail": "Tracks the latest saved result for this profile."},
        ],
    }
    return render_template("pages/practical.html", title="Practical",
                           practicals=[{"title": workspace["title"], "subject": subject["name"], "status": "In progress", "progress": subject["progress"], "href": "/practical"}],
                           workspace=workspace,
                           **shell_ctx("practical", user))


@app.route("/assignments")
@require_auth
def assignments():
    user = current_user()
    pending = sum(1 for a in M.ASSIGNMENTS if a["status"] != "Submitted")
    try:
        live_assignments = student_assignments(user["id"])
    except Exception:
        live_assignments = []
    try:
        live_announcements = student_announcements(user["id"])
    except Exception:
        live_announcements = []
    return render_template("pages/assignments.html", title="Assignments",
                           assignments=M.ASSIGNMENTS, assignment=M.ASSIGNMENT_WORKSPACE,
                           assignment_types=M.ASSIGNMENT_TYPES, pending=pending + len(live_assignments),
                           live_assignments=live_assignments, live_announcements=live_announcements,
                           **shell_ctx("assignments", user))


@app.get("/api/v1/assignments")
@require_auth
def api_student_assignments():
    return jsonify({"items": student_assignments(current_user()["id"])})


@app.get("/api/v1/announcements")
@require_auth
def api_student_announcements():
    return jsonify({"items": student_announcements(current_user()["id"])})


@app.route("/sandbox")
@require_auth
def sandbox():
    return render_template("pages/sandbox.html", title="Sandbox",
                           cards=M.SANDBOX_CARDS, **shell_ctx("sandbox", current_user()))


@app.get("/student/simulation/<simulation_id>")
@require_auth
def student_simulation(simulation_id):
    user = current_user()
    simulation = next((item for item in load_feature_simulations() if item.get("id") == simulation_id), None)
    if not simulation:
        return "Simulation not found.", 404
    if user.get("role") == "STUDENT" and not access_allowed(user["id"], "simulation", simulation_id):
        return "This simulation is currently unavailable.", 403
    return redirect(simulation["runtime_path"])


@app.route("/progress")
@require_auth
def progress():
    user = current_user()
    dashboard = build_user_progress_dashboard(user["id"])
    return render_template("pages/progress.html", title="Progress",
                           subjects=dashboard["subjects"], weekly=[],
                           progress_subjects=[{
                               "name": s["name"],
                               "slug": s["slug"],
                               "icon": s["icon"],
                               "bg": s["bg"],
                               "color": s["color"],
                               "progress": s["progress"],
                               "current_chapter": s["current_chapter"],
                               "modules": [{
                                   "title": "Current learning",
                                   "progress": s["progress"],
                                   "chapters": [{
                                       "title": s["current_chapter"],
                                       "progress": s["progress"],
                                       "status": "Completed" if s["progress"] >= 100 else ("In Progress" if s["progress"] > 0 else "Not started"),
                                       "activity": [
                                           {"name": "Lesson", "status": "Completed" if s["progress"] >= 100 else ("In progress" if s["progress"] > 0 else "Not started")},
                                           {"name": "Lab", "status": "Completed" if s["progress"] >= 100 else ("In progress" if s["progress"] > 0 else "Not started")},
                                       ]
                                   }]
                               }]
                           } for s in dashboard["subjects"]],
                           next_action=dashboard["next_action"], pending_work=dashboard["pending_work"],
                           activity_history=dashboard["activity_history"],
                           achievements=dashboard["achievements"], **shell_ctx("progress", user))


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
    user = current_user()
    payload = request.get_json(silent=True) or {}
    kind = payload.get("kind", "progress")
    record_id = str(payload.get("record_id", "")).strip()
    record = payload.get("payload", {})
    if not isinstance(record, dict):
        record = {"raw_payload": record}
    status = str(payload.get("status", "local"))
    client_event_id = str(payload.get("event_id") or payload.get("client_event_id") or "").strip() or None

    if not record_id or kind not in {"progress", "submission"}:
        return json_error("A valid local record is required.", "VALIDATION_ERROR", 400)

    if "user_id" not in record and user:
        record["user_id"] = user["id"]

    try:
        event_id = None
        if kind == "submission":
            save_local_submission(record_id, record_id, record, status=status)
        else:
            save_local_progress(record_id, record, sync_status="local")
            if record_id.startswith("lesson:") and user:
                lesson_id = record_id.split(":", 1)[1]
                visited = record.get("visited", [])
                percent = int(payload.get("percent_complete") or record.get("percent") or (len(visited) * 20 if isinstance(visited, list) else 0))
                prog_status = "completed" if (status in {"completed", "SUBMITTED", "submitted"} or record.get("done")) else ("practiced" if status == "practiced" else "in_progress")
                save_learning_progress(user["id"], lesson_id=lesson_id, status=prog_status, percent_complete=min(100, max(0, percent)))
                record_event(user["id"], "LESSON_COMPLETED" if prog_status == "completed" else "LESSON_STARTED",
                             activity_type="lesson", activity_id=lesson_id, detail=f"{lesson_id} · {prog_status}")

        if status in {"SUBMITTED", "submitted", "completed"} or kind == "submission":
            event_id = enqueue_sync_event(kind, record_id, "upsert", record, event_id=client_event_id)
            if user:
                record_event(user["id"], "ASSIGNMENT_SUBMITTED" if kind == "submission" else "ACTIVITY_COMPLETED",
                             activity_type=kind, activity_id=record_id, detail=f"{record_id} saved locally")
    except ValueError as exc:
        return json_error(str(exc) or "A valid local record is required.", "VALIDATION_ERROR", 400)

    return json_success("Local state saved.", "LOCAL_STATE_SAVED", {
        "storage": "sqlite",
        "sync_status": "queued" if (kind == "submission" or status in {"SUBMITTED", "submitted", "completed"}) else "local",
        "event_id": event_id or client_event_id,
    }, 200)



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
    from app.services.content_catalog import list_questions, list_subjects
    try:
        subjects = list_subjects()
    except Exception:
        subjects = []
    selected = request.args.get("subject", "").strip()
    try:
        questions = list_questions(selected or None)[:10]
    except Exception:
        questions = []
    # Strip answers before rendering; checking goes through /api/v1/quizzes/check.
    public = [{
        "question_id": q.get("question_id"),
        "prompt": q.get("prompt"),
        "question_type": q.get("question_type"),
        "options": [{"option_id": o.get("option_id"), "option_text": o.get("option_text")}
                    for o in q.get("options", [])],
    } for q in questions]
    return render_template("pages/tests.html", title="Tests", quiz_subjects=subjects,
                           selected_subject=selected, quiz_questions=public,
                           **shell_ctx("tests", current_user()))


@app.route("/ask-ai")
@require_auth
def ask_ai():
    lesson_id = request.args.get("lesson_id", "").strip()
    lesson = None
    if lesson_id:
        # Accept both catalog lesson ids and legacy demo ids (e.g. friction-43).
        lesson = get_academic_lesson(lesson_id) or L.get_lesson(lesson_id)
        if isinstance(lesson, dict) and "lesson_id" not in lesson and lesson.get("id"):
            lesson = {**lesson, "lesson_id": lesson["id"],
                      "subject_name": lesson.get("subject_name", ""),
                      "chapter_label": lesson.get("chapter_label", ""),
                      "topic_title": lesson.get("title", "")}
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
