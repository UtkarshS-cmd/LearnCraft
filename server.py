import os
import json
from flask import Flask, request, redirect, render_template, jsonify

from database import (
    initialize_database,
    add_student,
    get_students,
    ensure_note_seed,
    get_notes,
    create_note,
    update_note,
    set_note_pinned,
    delete_note,
    upsert_content_item,
    save_local_progress,
    save_local_submission,
    enqueue_sync_event,
    get_offline_status
)
import mock_data as M
import lessons_data as L

app = Flask(__name__)

initialize_database()

NETWORK_MODE = os.environ.get("LEARNCRAFT_NETWORK_MODE", "OFFLINE").upper()
MASTER_URL = os.environ.get("LEARNCRAFT_MASTER_URL", "").strip()


def seed_local_content():
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


def shell_ctx(active):
    pending = sum(1 for a in M.ASSIGNMENTS if a["status"] != "Submitted")
    return dict(nav=M.NAV, student=M.STUDENT, active=active, pending_count=pending)


# ---- Legacy portal (kept): student login + teacher view ----
@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LearnCraft</title>
    </head>

    <body>

        <h1>LearnCraft</h1>
        <h2>Offline Learning OS</h2>

        <hr>

        <h3>Student Login</h3>

        <form action="/join" method="POST">

            <label>Name:</label><br>
            <input type="text" name="name" required>

            <br><br>

            <label>Roll Number:</label><br>
            <input type="text" name="roll_no" required>

            <br><br>

            <button type="submit">
                Join Lab
            </button>

        </form>

        <hr>

        <a href="/teacher">
            Teacher Dashboard
        </a>
        &nbsp;·&nbsp;
        <a href="/home">
            Student App →
        </a>

    </body>
    </html>
    """


@app.route("/join", methods=["POST"])
def join():

    name = request.form["name"]
    roll_no = request.form["roll_no"]

    add_student(name, roll_no)

    return redirect("/home")


@app.route("/teacher")
def teacher():

    students = get_students()

    rows = ""

    for student in students:
        rows += f"""
        <tr>
            <td>{student["roll_no"]}</td>
            <td>{student["name"]}</td>
            <td>🟢 Connected</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>

    <html>

    <head>
        <title>Teacher Dashboard</title>
    </head>

    <body>

        <h1>LearnCraft — Teacher Dashboard</h1>

        <h3>
            Students Registered: {len(students)}
        </h3>

        <table border="1" cellpadding="10">

            <tr>
                <th>Roll No</th>
                <th>Name</th>
                <th>Status</th>
            </tr>

            {rows}

        </table>

        <br>

        <a href="/">
            Student Portal
        </a>

    </body>

    </html>
    """


# ---- Student App Shell (new, offline-first, mock data) ----
@app.route("/home")
def student_home():
    ctx = shell_ctx("home")
    pending_assign = sum(1 for a in M.ASSIGNMENTS if a["status"] != "Submitted")
    pending_practicals = sum(1 for p in M.PRACTICALS if p["status"] != "Completed")
    return render_template("pages/home.html", title="Home",
                           cont=M.CONTINUE_LEARNING, today_work=M.TODAY_WORK,
                           my_subjects=M.SUBJECTS[:4], activity=M.ACTIVITY,
                           pending_assign=pending_assign,
                           pending_practicals=pending_practicals,
                           greeting_sub="Tue · Lab A · Period 3 — 2 items need attention today.",
                           **ctx)


@app.route("/my-learning")
def my_learning():
    return render_template("pages/my_learning.html", title="My Learning",
                           items=M.MY_LEARNING, cont=M.CONTINUE_LEARNING,
                           lesson_map=L.FIRST_LESSON, **shell_ctx("my-learning"))


@app.route("/subjects")
def subjects():
    return render_template("pages/subjects.html", title="Subjects",
                           subjects=M.SUBJECTS, **shell_ctx("subjects"))


@app.route("/subjects/<slug>")
def subject_detail(slug):
    page = M.get_subject_page(slug)
    if page is None:
        return redirect("/subjects")
    page = dict(page)
    first = L.FIRST_LESSON.get(slug)
    if first:
        page["continue"] = dict(page["continue"], href=f"/subjects/{slug}/lessons/{first}")
    return render_template("pages/subject_detail.html", title=page["name"],
                           page=page, first_lesson=first, **shell_ctx("subjects"))


@app.route("/subjects/<slug>/lessons/<lesson_id>")
def lesson_player(slug, lesson_id):
    lesson = L.get_lesson(lesson_id)
    if lesson is None or lesson["subject_slug"] != slug:
        return redirect(f"/subjects/{slug}")
    seen, stages = set(), []
    for b in lesson["blocks"]:
        if b["stage"] not in seen:
            seen.add(b["stage"])
            stages.append(b["stage"])
    return render_template("pages/lesson.html", title=lesson["title"],
                           lesson=lesson, stages=stages, **shell_ctx("subjects"))


@app.route("/practical")
def practical():
    return render_template("pages/practical.html", title="Practical",
                           practicals=M.PRACTICALS, workspace=M.PRACTICAL_WORKSPACE,
                           **shell_ctx("practical"))


@app.route("/assignments")
def assignments():
    pending = sum(1 for a in M.ASSIGNMENTS if a["status"] != "Submitted")
    return render_template("pages/assignments.html", title="Assignments",
                           assignments=M.ASSIGNMENTS, assignment=M.ASSIGNMENT_WORKSPACE,
                           assignment_types=M.ASSIGNMENT_TYPES, pending=pending,
                           **shell_ctx("assignments"))


@app.route("/sandbox")
def sandbox():
    return render_template("pages/sandbox.html", title="Sandbox",
                           cards=M.SANDBOX_CARDS, **shell_ctx("sandbox"))


@app.route("/progress")
def progress():
    return render_template("pages/progress.html", title="Progress",
                           subjects=M.SUBJECTS, weekly=M.WEEKLY,
                           progress_subjects=M.PROGRESS_SUBJECTS,
                           next_action=M.PROGRESS_NEXT, pending_work=M.PROGRESS_PENDING,
                           activity_history=M.PROGRESS_ACTIVITY,
                           achievements=M.ACHIEVEMENTS, **shell_ctx("progress"))


@app.route("/notes")
def notes():
    ensure_note_seed(M.NOTES_SEED)
    search = request.args.get("q", "").strip()
    subject = request.args.get("subject", "").strip()
    return render_template("pages/notes.html", title="Notes",
                           subjects=M.SUBJECTS, notes=get_notes(search, subject),
                           search=search, selected_subject=subject,
                           context={"subject": request.args.get("context_subject", ""),
                                    "chapter": request.args.get("context_chapter", ""),
                                    "source_type": request.args.get("source_type", ""),
                                    "source_id": request.args.get("source_id", ""),
                                    "source_title": request.args.get("source_title", "")},
                           **shell_ctx("notes"))


@app.post("/api/notes")
def api_create_note():
    payload = request.get_json(silent=True) or {}
    title, body, subject = (str(payload.get(key, "")).strip() for key in ("title", "body", "subject"))
    if not title or not subject:
        return jsonify({"error": "Title and subject are required."}), 400
    return jsonify(create_note(title, body, subject, payload.get("chapter"),
                               payload.get("source_type"), payload.get("source_id"),
                               payload.get("source_title"))), 201


@app.put("/api/notes/<client_id>")
def api_update_note(client_id):
    payload = request.get_json(silent=True) or {}
    title, body, subject = (str(payload.get(key, "")).strip() for key in ("title", "body", "subject"))
    if not title or not subject:
        return jsonify({"error": "Title and subject are required."}), 400
    note = update_note(client_id, title, body, subject, payload.get("chapter"))
    return jsonify(note) if note else (jsonify({"error": "Note not found."}), 404)


@app.post("/api/notes/<client_id>/pin")
def api_pin_note(client_id):
    payload = request.get_json(silent=True) or {}
    note = set_note_pinned(client_id, bool(payload.get("pinned")))
    return jsonify(note) if note else (jsonify({"error": "Note not found."}), 404)


@app.delete("/api/notes/<client_id>")
def api_delete_note(client_id):
    delete_note(client_id)
    return jsonify({"ok": True})


@app.get("/api/system/status")
def api_system_status():
    return jsonify({
        "mode": NETWORK_MODE if NETWORK_MODE in {"OFFLINE", "LOCAL_NETWORK", "INTERNET"} else "OFFLINE",
        "internet_enabled": False,
        "master_configured": bool(MASTER_URL),
        "core_storage": "sqlite",
        "asset_storage": "local-filesystem",
        **get_offline_status()
    })


@app.post("/api/local/state")
def api_local_state():
    payload = request.get_json(silent=True) or {}
    kind = payload.get("kind", "progress")
    record_id = str(payload.get("record_id", "")).strip()
    record = payload.get("payload", {})
    status = payload.get("status", "local")
    if not record_id or kind not in {"progress", "submission"}:
        return jsonify({"error": "A valid local record is required."}), 400
    if kind == "submission":
        save_local_submission(record_id, record_id, record, status=status)
    else:
        save_local_progress(record_id, record, sync_status="local")
    if status in {"SUBMITTED", "submitted", "completed"} or kind == "submission":
        enqueue_sync_event(kind, record_id, "upsert", record)
    return jsonify({"ok": True, "storage": "sqlite", "sync_status": "queued" if kind == "submission" else "local"})


@app.get("/api/content/catalog")
def api_content_catalog():
    from database import get_connection
    connection = get_connection()
    rows = connection.execute(
        "SELECT content_id, kind, subject_slug, title, payload_json, asset_path, content_version, source FROM content_items ORDER BY kind, title"
    ).fetchall()
    connection.close()
    return jsonify([{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows])


@app.get("/api/sync/queue")
def api_sync_queue():
    from database import get_connection
    connection = get_connection()
    rows = connection.execute(
        "SELECT event_id, entity_type, entity_id, operation, payload_json, status, created_at FROM sync_queue WHERE status = 'queued' ORDER BY id"
    ).fetchall()
    connection.close()
    return jsonify([{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows])


@app.route("/profile")
def profile():
    return render_template("pages/profile.html", title="Profile", **shell_ctx("profile"))


if __name__ == "__main__":

    print("--------------------------------")
    print(" LearnCraft Local Server")
    print("--------------------------------")
    print("Server starting...")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
