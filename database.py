import sqlite3
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "learncraft.db"


def get_connection():
    DATA_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL,
            chapter TEXT,
            source_type TEXT,
            source_id TEXT,
            source_title TEXT,
            pinned INTEGER NOT NULL DEFAULT 0,
            sync_status TEXT NOT NULL DEFAULT 'local',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            subject_slug TEXT,
            title TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            asset_path TEXT,
            content_version TEXT NOT NULL DEFAULT '1',
            source TEXT NOT NULL DEFAULT 'local',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS local_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL DEFAULT '{}',
            sync_status TEXT NOT NULL DEFAULT 'local',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS local_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id TEXT NOT NULL UNIQUE,
            activity_id TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'draft',
            sync_status TEXT NOT NULL DEFAULT 'local',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            attempted_at TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def add_student(name, roll_no):
    connection = get_connection()

    connection.execute(
        "INSERT INTO students (name, roll_no) VALUES (?, ?)",
        (name, roll_no)
    )

    connection.commit()
    connection.close()


def get_students():
    connection = get_connection()

    students = connection.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()

    connection.close()

    return students


def _note_dict(row):
    return dict(row) if row else None


def ensure_note_seed(notes):
    connection = get_connection()
    count = connection.execute("SELECT COUNT(*) FROM notes WHERE deleted_at IS NULL").fetchone()[0]
    if count == 0:
        for note in notes:
            connection.execute(
                """INSERT INTO notes
                (client_id, title, body, subject, chapter, pinned, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, 'local')""",
                (str(uuid.uuid4()), note["title"], note["body"], note["subject"], note.get("chapter"), 0)
            )
        connection.commit()
    connection.close()


def get_notes(search="", subject="", pinned_only=False):
    connection = get_connection()
    clauses = ["deleted_at IS NULL"]
    params = []
    if search:
        clauses.append("(title LIKE ? OR body LIKE ? OR chapter LIKE ? OR source_title LIKE ?)")
        value = f"%{search}%"
        params.extend([value, value, value, value])
    if subject:
        clauses.append("subject = ?")
        params.append(subject)
    if pinned_only:
        clauses.append("pinned = 1")
    notes = connection.execute(
        f"SELECT * FROM notes WHERE {' AND '.join(clauses)} ORDER BY pinned DESC, updated_at DESC, id DESC",
        params
    ).fetchall()
    connection.close()
    return [_note_dict(note) for note in notes]


def create_note(title, body, subject, chapter=None, source_type=None, source_id=None, source_title=None):
    connection = get_connection()
    client_id = str(uuid.uuid4())
    connection.execute(
        """INSERT INTO notes
        (client_id, title, body, subject, chapter, source_type, source_id, source_title, sync_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'local')""",
        (client_id, title, body, subject, chapter, source_type, source_id, source_title)
    )
    connection.commit()
    note = connection.execute("SELECT * FROM notes WHERE client_id = ?", (client_id,)).fetchone()
    connection.close()
    return _note_dict(note)


def update_note(client_id, title, body, subject, chapter=None):
    connection = get_connection()
    connection.execute(
        """UPDATE notes SET title = ?, body = ?, subject = ?, chapter = ?,
        updated_at = CURRENT_TIMESTAMP, sync_status = 'local'
        WHERE client_id = ? AND deleted_at IS NULL""",
        (title, body, subject, chapter, client_id)
    )
    connection.commit()
    note = connection.execute("SELECT * FROM notes WHERE client_id = ?", (client_id,)).fetchone()
    connection.close()
    return _note_dict(note)


def set_note_pinned(client_id, pinned):
    connection = get_connection()
    connection.execute(
        """UPDATE notes SET pinned = ?, updated_at = CURRENT_TIMESTAMP, sync_status = 'local'
        WHERE client_id = ? AND deleted_at IS NULL""",
        (1 if pinned else 0, client_id)
    )
    connection.commit()
    note = connection.execute("SELECT * FROM notes WHERE client_id = ?", (client_id,)).fetchone()
    connection.close()
    return _note_dict(note)


def delete_note(client_id):
    connection = get_connection()
    connection.execute(
        """UPDATE notes SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
        sync_status = 'local' WHERE client_id = ?""",
        (client_id,)
    )
    connection.commit()
    connection.close()


def upsert_content_item(content_id, kind, title, payload, subject_slug=None, asset_path=None, version="1"):
    import json
    connection = get_connection()
    connection.execute(
        """INSERT INTO content_items
        (content_id, kind, subject_slug, title, payload_json, asset_path, content_version, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'local')
        ON CONFLICT(content_id) DO UPDATE SET kind=excluded.kind,
        subject_slug=excluded.subject_slug, title=excluded.title, payload_json=excluded.payload_json,
        asset_path=excluded.asset_path, content_version=excluded.content_version,
        updated_at=CURRENT_TIMESTAMP""",
        (content_id, kind, subject_slug, title, json.dumps(payload), asset_path, version)
    )
    connection.commit()
    connection.close()


def save_local_progress(record_id, payload, sync_status="local"):
    import json
    connection = get_connection()
    connection.execute(
        """INSERT INTO local_progress (record_id, payload_json, sync_status)
        VALUES (?, ?, ?) ON CONFLICT(record_id) DO UPDATE SET payload_json=excluded.payload_json,
        sync_status=excluded.sync_status, updated_at=CURRENT_TIMESTAMP""",
        (record_id, json.dumps(payload), sync_status)
    )
    connection.commit()
    connection.close()


def save_local_submission(submission_id, activity_id, payload, status="draft", sync_status="local"):
    import json
    connection = get_connection()
    connection.execute(
        """INSERT INTO local_submissions (submission_id, activity_id, payload_json, status, sync_status)
        VALUES (?, ?, ?, ?, ?) ON CONFLICT(submission_id) DO UPDATE SET payload_json=excluded.payload_json,
        status=excluded.status, sync_status=excluded.sync_status, updated_at=CURRENT_TIMESTAMP""",
        (submission_id, activity_id, json.dumps(payload), status, sync_status)
    )
    connection.commit()
    connection.close()


def enqueue_sync_event(entity_type, entity_id, operation, payload):
    import json
    event_id = str(uuid.uuid4())
    connection = get_connection()
    connection.execute(
        """INSERT INTO sync_queue (event_id, entity_type, entity_id, operation, payload_json)
        VALUES (?, ?, ?, ?, ?)""",
        (event_id, entity_type, entity_id, operation, json.dumps(payload))
    )
    connection.commit()
    connection.close()
    return event_id


def get_offline_status():
    connection = get_connection()
    counts = {
        "queued_sync": connection.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'queued'").fetchone()[0],
        "content_items": connection.execute("SELECT COUNT(*) FROM content_items WHERE source = 'local'").fetchone()[0],
        "local_progress": connection.execute("SELECT COUNT(*) FROM local_progress").fetchone()[0],
        "local_submissions": connection.execute("SELECT COUNT(*) FROM local_submissions").fetchone()[0],
    }
    connection.close()
    return counts