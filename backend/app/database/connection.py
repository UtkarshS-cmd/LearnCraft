import json
import os
import sqlite3
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def _candidate_db_paths():
    """All locations that may already hold a LearnCraft database."""
    configured = os.environ.get("LEARNCRAFT_DB_PATH")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            # Resolve repository-relative paths (e.g. "data/learncraft.db")
            # against the project root so the app works no matter which
            # directory the server was started from.
            candidate = (BASE_DIR / candidate).resolve()
        yield candidate
    yield (DATA_DIR / "learncraft.db").resolve()


def resolve_db_path():
    configured = os.environ.get("LEARNCRAFT_DB_PATH")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            return (BASE_DIR / candidate).resolve()
        return candidate
    return DATA_DIR / "learncraft.db"


def get_connection():
    db_path = resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error:
        pass
    return connection


def _repair_corrupt_password_hashes(connection):
    """Reset legacy/corrupt password hashes so existing accounts can log in.

    Older builds wrote placeholder values (e.g. ``'x'``) into
    ``users.password_hash``. Those rows can never authenticate with any
    password, which looked like "login is broken for an existing account".
    Affected rows get a random unusable hash plus a fresh profile row so the
    normal offline Forgot-password (OTP) flow can recover the account.
    """
    from werkzeug.security import gen_salt

    rows = connection.execute(
        "SELECT id FROM users WHERE password_hash IS NULL OR password_hash = '' "
        "OR password_hash NOT LIKE 'scrypt:%' AND password_hash NOT LIKE 'pbkdf2:%'"
    ).fetchall()
    if not rows:
        return
    for row in rows:
        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (f"scrypt:32768:8:1${gen_salt(32)}${gen_salt(32)}", row["id"]),
        )
        # Merge the reset flag into the profile; plain INSERT OR IGNORE would
        # silently skip users that already have a profile row.
        existing = connection.execute(
            "SELECT preferences_json FROM user_profiles WHERE user_id = ?", (row["id"],)
        ).fetchone()
        if existing:
            try:
                prefs = json.loads(existing["preferences_json"] or "{}")
            except (TypeError, ValueError):
                prefs = {}
            prefs["password_reset_required"] = True
            connection.execute(
                "UPDATE user_profiles SET preferences_json = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ?",
                (json.dumps(prefs), row["id"]),
            )
        else:
            connection.execute(
                "INSERT INTO user_profiles (user_id, preferences_json, created_at, updated_at) "
                "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (row["id"], json.dumps({"theme": "system", "offline_mode": True, "password_reset_required": True})),
            )
    try:
        connection.commit()
    except sqlite3.Error:
        pass


def initialize_database():
    connection = get_connection()
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'STUDENT',
            avatar TEXT,
            bio TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            roll_no TEXT,
            student_class TEXT,
            timezone TEXT,
            preferences_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_slug TEXT,
            chapter_id TEXT,
            lesson_id TEXT,
            status TEXT NOT NULL DEFAULT 'not_started',
            percent_complete INTEGER NOT NULL DEFAULT 0,
            score REAL DEFAULT 0,
            last_activity TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, lesson_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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
            attempted_at TIMESTAMP,
            user_id INTEGER
        )
    """)
    # Additive migration for databases created before queue events were owned.
    sync_queue_columns = {row[1] for row in connection.execute("PRAGMA table_info(sync_queue)").fetchall()}
    if "user_id" not in sync_queue_columns:
        connection.execute("ALTER TABLE sync_queue ADD COLUMN user_id INTEGER")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_user ON sync_queue(user_id)")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_subjects (
            subject_id TEXT PRIMARY KEY,
            board TEXT NOT NULL,
            class_level TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            source_version TEXT NOT NULL,
            UNIQUE(board, class_level, academic_year, slug)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_books (
            book_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            title TEXT NOT NULL,
            publisher TEXT NOT NULL,
            source_reference TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES academic_subjects(subject_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_chapters (
            chapter_id TEXT PRIMARY KEY,
            book_id TEXT NOT NULL,
            chapter_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            source_reference TEXT NOT NULL,
            FOREIGN KEY(book_id) REFERENCES academic_books(book_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_topics (
            topic_id TEXT PRIMARY KEY,
            chapter_id TEXT NOT NULL,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            FOREIGN KEY(chapter_id) REFERENCES academic_chapters(chapter_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_lessons (
            lesson_id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            summary TEXT NOT NULL,
            learning_objectives_json TEXT NOT NULL,
            prerequisites_json TEXT NOT NULL,
            estimated_minutes INTEGER NOT NULL,
            difficulty TEXT NOT NULL,
            content_blocks_json TEXT NOT NULL,
            source_reference TEXT NOT NULL,
            FOREIGN KEY(topic_id) REFERENCES academic_topics(topic_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_concepts (
            concept_id TEXT PRIMARY KEY,
            lesson_id TEXT NOT NULL,
            title TEXT NOT NULL,
            explanation TEXT NOT NULL,
            FOREIGN KEY(lesson_id) REFERENCES academic_lessons(lesson_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_questions (
            question_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            chapter_id TEXT NOT NULL,
            topic_id TEXT,
            concept_id TEXT,
            difficulty TEXT NOT NULL,
            question_type TEXT NOT NULL,
            marks INTEGER NOT NULL,
            source_reference TEXT NOT NULL,
            source_year TEXT,
            skill TEXT NOT NULL,
            prompt TEXT NOT NULL,
            answer TEXT NOT NULL,
            explanation TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES academic_subjects(subject_id),
            FOREIGN KEY(chapter_id) REFERENCES academic_chapters(chapter_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_question_options (
            question_id TEXT NOT NULL,
            option_id TEXT NOT NULL,
            option_text TEXT NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(question_id, option_id),
            FOREIGN KEY(question_id) REFERENCES academic_questions(question_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_practice_sets (
            practice_set_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            chapter_id TEXT,
            title TEXT NOT NULL,
            practice_type TEXT NOT NULL,
            question_ids_json TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES academic_subjects(subject_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS academic_tests (
            test_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            chapter_id TEXT,
            title TEXT NOT NULL,
            test_type TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            marks INTEGER NOT NULL,
            question_ids_json TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES academic_subjects(subject_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS content_manifests (
            content_id TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            checksum TEXT NOT NULL,
            downloaded INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS ai_conversations (
            conversation_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'Learning chat',
            context_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS ai_messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            context_reference TEXT,
            provider TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES ai_conversations(conversation_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS external_resources (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL UNIQUE,
            subject TEXT NOT NULL DEFAULT '',
            class_level TEXT NOT NULL DEFAULT '',
            chapter TEXT NOT NULL DEFAULT '',
            topic TEXT NOT NULL DEFAULT '',
            concept_ids_json TEXT NOT NULL DEFAULT '[]',
            language TEXT NOT NULL DEFAULT 'en',
            difficulty TEXT NOT NULL DEFAULT 'FOUNDATION',
            is_official INTEGER NOT NULL DEFAULT 1,
            requires_login INTEGER NOT NULL DEFAULT 0,
            embed_supported INTEGER NOT NULL DEFAULT 0,
            offline_supported INTEGER NOT NULL DEFAULT 0,
            verified INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS resource_bookmarks (
            user_id INTEGER NOT NULL,
            resource_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
            pinned INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, resource_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (resource_id) REFERENCES external_resources(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS resource_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resource_id TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            concept_id TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_extres_provider ON external_resources(provider)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_extres_subject ON external_resources(subject)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_extres_enabled ON external_resources(enabled, verified)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_resact_user ON resource_activity(user_id)")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    connection.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_progress_user ON learning_progress(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_learning_progress_subject ON learning_progress(subject_slug)")
    chapter_indexes = connection.execute("PRAGMA index_list(academic_chapters)").fetchall()
    if any(row[2] and row[3] == "u" for row in chapter_indexes):
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("""
            CREATE TABLE academic_chapters_migrated (
                chapter_id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                slug TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                source_reference TEXT NOT NULL,
                FOREIGN KEY(book_id) REFERENCES academic_books(book_id)
            )
        """)
        connection.execute("INSERT INTO academic_chapters_migrated SELECT * FROM academic_chapters")
        connection.execute("DROP TABLE academic_chapters")
        connection.execute("ALTER TABLE academic_chapters_migrated RENAME TO academic_chapters")
    note_columns = {row[1] for row in connection.execute("PRAGMA table_info(notes)").fetchall()}
    if "user_id" not in note_columns:
        connection.execute("ALTER TABLE notes ADD COLUMN user_id INTEGER")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_conversations_user ON ai_conversations(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_messages_conversation ON ai_messages(conversation_id)")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS teacher_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            grade TEXT,
            section TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS class_members (
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (class_id, student_id),
            FOREIGN KEY (class_id) REFERENCES teacher_classes(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            subject_slug TEXT,
            activity_type TEXT,
            activity_id TEXT,
            detail TEXT NOT NULL DEFAULT '',
            score REAL,
            duration_seconds INTEGER,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS access_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_by INTEGER NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(scope_type, scope_id, resource_type, resource_id),
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS teacher_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_id INTEGER,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            title TEXT NOT NULL,
            start_at TIMESTAMP,
            due_at TIMESTAMP,
            attempts INTEGER,
            difficulty TEXT,
            time_limit_minutes INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES teacher_classes(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS assignment_targets (
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            PRIMARY KEY (assignment_id, student_id),
            FOREIGN KEY (assignment_id) REFERENCES teacher_assignments(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS teacher_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_id INTEGER,
            message TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES teacher_classes(id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS teacher_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            event_id INTEGER,
            kind TEXT NOT NULL,
            message TEXT NOT NULL,
            read_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES activity_events(id) ON DELETE SET NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS teacher_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            scope TEXT NOT NULL,
            previous_state TEXT,
            new_state TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_activity_events_user_time ON activity_events(user_id, created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_activity_events_type_time ON activity_events(event_type, created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_class_members_student ON class_members(student_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_teacher_notifications_teacher ON teacher_notifications(teacher_id, created_at)")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS student_join_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            class_id INTEGER,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            decided_at TIMESTAMP,
            UNIQUE(student_id, teacher_id),
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES teacher_classes(id) ON DELETE SET NULL
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_join_requests_teacher ON student_join_requests(teacher_id, status)")

    _repair_corrupt_password_hashes(connection)

    connection.commit()
    connection.close()


def _transaction(work):
    """Run DB work with commit/rollback and always close the connection."""
    connection = get_connection()
    try:
        result = work(connection)
        connection.commit()
        return result
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        raise
    finally:
        connection.close()


def add_student(name, roll_no):
    connection = get_connection()
    connection.execute(
        "INSERT INTO students (name, roll_no) VALUES (?, ?)",
        (name, roll_no),
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


def get_users():
    connection = get_connection()
    users = connection.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    connection.close()
    return [_row_to_dict(user) for user in users]


def get_student(user_id):
    connection = get_connection()
    student = connection.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
    connection.close()
    return _row_to_dict(student)


def _row_to_dict(row):
    return dict(row) if row else None


def _initials_from_name(name):
    pieces = [part for part in str(name or "").strip().split() if part]
    if not pieces:
        return "LC"
    initials = "".join(part[0].upper() for part in pieces[:2])
    return initials[:2] or "LC"


def create_user(name, email, password_hash, role="STUDENT", avatar=None):
    def work(connection):
        cleaned_name = str(name or "").strip()
        cleaned_email = str(email or "").strip().lower()
        avatar_value = (avatar or _initials_from_name(cleaned_name)).upper()
        cursor = connection.execute(
            """
            INSERT INTO users (name, email, password_hash, role, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (cleaned_name, cleaned_email, password_hash, str(role).upper(), avatar_value),
        )
        user_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO user_profiles (user_id, preferences_json, created_at, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (user_id, json.dumps({"theme": "system", "offline_mode": True})),
        )
        return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_dict(_transaction(work))


def get_user_by_email(email):
    connection = get_connection()
    user = connection.execute("SELECT * FROM users WHERE email = ?", (str(email or "").strip().lower(),)).fetchone()
    connection.close()
    return _row_to_dict(user)


def create_password_reset_token(user_id, token_hash, expires_at):
    def work(connection):
        connection.execute(
            "UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP WHERE user_id = ? AND used_at IS NULL",
            (int(user_id),),
        )
        cursor = connection.execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (int(user_id), token_hash, expires_at),
        )
        return cursor.lastrowid
    return _transaction(work)


def consume_password_reset_token(user_id, token_hash):
    def work(connection):
        token = connection.execute(
            """
            SELECT id FROM password_reset_tokens
            WHERE user_id = ? AND token_hash = ? AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP
            ORDER BY id DESC LIMIT 1
            """,
            (int(user_id), token_hash),
        ).fetchone()
        if token:
            connection.execute(
                "UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP WHERE id = ?",
                (token["id"],),
            )
        return bool(token)
    return _transaction(work)


def update_user_password(user_id, password_hash):
    def work(connection):
        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (password_hash, int(user_id)),
        )
    _transaction(work)


def get_user_by_id(user_id):
    connection = get_connection()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
    connection.close()
    return _row_to_dict(user)


def user_payload(user):
    if not user:
        return None
    user_data = dict(user)
    user_data.pop("password_hash", None)
    return user_data


def update_user_profile(user_id, *, name=None, email=None, avatar=None, bio=None):
    def work(connection):
        payload = {} 
        if name is not None:
            payload["name"] = str(name).strip()
        if email is not None:
            cleaned = str(email).strip().lower()
            existing = connection.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?", (cleaned, int(user_id))
            ).fetchone()
            if existing:
                raise ValueError("An account with this email already exists.")
            payload["email"] = cleaned
        if avatar is not None:
            payload["avatar"] = str(avatar).strip()[:2].upper()
        if bio is not None:
            payload["bio"] = str(bio).strip()[:200]
        if not payload:
            return connection.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()

        assignments = []
        values = []
        for key, value in payload.items():
            assignments.append(f"{key} = ?")
            values.append(value)
        values.append(int(user_id))
        connection.execute(
            f"UPDATE users SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        return connection.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
    return _row_to_dict(_transaction(work))


def get_user_progress(user_id):
    connection = get_connection()
    rows = connection.execute(
        "SELECT * FROM learning_progress WHERE user_id = ? ORDER BY updated_at DESC",
        (int(user_id),),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def save_learning_progress(user_id, *, subject_slug=None, chapter_id=None, lesson_id=None, status="not_started", percent_complete=0, score=0, last_activity=None):
    def work(connection):
        if not lesson_id:
            raise ValueError("lesson_id is required.")
        connection.execute(
            """
            INSERT INTO learning_progress (user_id, subject_slug, chapter_id, lesson_id, status, percent_complete, score, last_activity, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, lesson_id) DO UPDATE SET
                subject_slug = excluded.subject_slug,
                chapter_id = excluded.chapter_id,
                status = excluded.status,
                percent_complete = excluded.percent_complete,
                score = excluded.score,
                last_activity = excluded.last_activity,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(user_id), subject_slug, chapter_id, lesson_id, status, int(percent_complete), float(score or 0), last_activity),
        )
    _transaction(work)


def ensure_note_seed(user_id, notes):
    def work(connection):
        count = connection.execute(
            "SELECT COUNT(*) FROM notes WHERE user_id = ? AND deleted_at IS NULL", (int(user_id),)
        ).fetchone()[0]
        if count == 0:
            for note in notes:
                connection.execute(
                    """INSERT INTO notes
                    (user_id, client_id, title, body, subject, chapter, pinned, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'local')""",
                    (int(user_id), str(uuid.uuid4()), note["title"], note["body"], note["subject"], note.get("chapter"), 0),
                )
    _transaction(work)


def get_notes(user_id, search="", subject="", pinned_only=False):
    connection = get_connection()
    clauses = ["user_id = ?", "deleted_at IS NULL"]
    params = [int(user_id)]
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
        params,
    ).fetchall()
    connection.close()
    return [_row_to_dict(note) for note in notes]


def create_note(user_id, title, body, subject, chapter=None, source_type=None, source_id=None, source_title=None):
    def work(connection):
        client_id = str(uuid.uuid4())
        connection.execute(
            """INSERT INTO notes
            (user_id, client_id, title, body, subject, chapter, source_type, source_id, source_title, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'local')""",
            (int(user_id), client_id, title, body, subject, chapter, source_type, source_id, source_title),
        )
        return connection.execute("SELECT * FROM notes WHERE client_id = ?", (client_id,)).fetchone()
    return _row_to_dict(_transaction(work))


def update_note(user_id, client_id, title, body, subject, chapter=None):
    def work(connection):
        connection.execute(
            """UPDATE notes SET title = ?, body = ?, subject = ?, chapter = ?,
            updated_at = CURRENT_TIMESTAMP, sync_status = 'local'
            WHERE client_id = ? AND user_id = ? AND deleted_at IS NULL""",
            (title, body, subject, chapter, client_id, int(user_id)),
        )
        return connection.execute("SELECT * FROM notes WHERE client_id = ?", (client_id,)).fetchone()
    return _row_to_dict(_transaction(work))


def set_note_pinned(user_id, client_id, pinned):
    def work(connection):
        connection.execute(
            """UPDATE notes SET pinned = ?, updated_at = CURRENT_TIMESTAMP, sync_status = 'local'
            WHERE client_id = ? AND user_id = ? AND deleted_at IS NULL""",
            (1 if pinned else 0, client_id, int(user_id)),
        )
        return connection.execute("SELECT * FROM notes WHERE client_id = ?", (client_id,)).fetchone()
    return _row_to_dict(_transaction(work))


def delete_note(user_id, client_id):
    def work(connection):
        connection.execute(
            """UPDATE notes SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
            sync_status = 'local' WHERE client_id = ? AND user_id = ?""",
            (client_id, int(user_id)),
        )
    _transaction(work)


def upsert_content_item(content_id, kind, title, payload, subject_slug=None, asset_path=None, version="1"):
    def work(connection):
        connection.execute(
            """INSERT INTO content_items
            (content_id, kind, subject_slug, title, payload_json, asset_path, content_version, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'local')
            ON CONFLICT(content_id) DO UPDATE SET kind=excluded.kind,
            subject_slug=excluded.subject_slug, title=excluded.title, payload_json=excluded.payload_json,
            asset_path=excluded.asset_path, content_version=excluded.content_version,
            updated_at=CURRENT_TIMESTAMP""",
            (content_id, kind, subject_slug, title, json.dumps(payload), asset_path, version),
        )
    _transaction(work)


def save_local_progress(record_id, payload, sync_status="local"):
    def work(connection):
        if not record_id:
            raise ValueError("record_id is required.")
        connection.execute(
            """INSERT INTO local_progress (record_id, payload_json, sync_status)
            VALUES (?, ?, ?) ON CONFLICT(record_id) DO UPDATE SET payload_json=excluded.payload_json,
            sync_status=excluded.sync_status, updated_at=CURRENT_TIMESTAMP""",
            (record_id, json.dumps(payload), sync_status),
        )
    _transaction(work)


def save_local_submission(submission_id, activity_id, payload, status="draft", sync_status="local"):
    def work(connection):
        if not submission_id:
            raise ValueError("submission_id is required.")
        connection.execute(
            """INSERT INTO local_submissions (submission_id, activity_id, payload_json, status, sync_status)
            VALUES (?, ?, ?, ?, ?) ON CONFLICT(submission_id) DO UPDATE SET payload_json=excluded.payload_json,
            status=excluded.status, sync_status=excluded.sync_status, updated_at=CURRENT_TIMESTAMP""",
            (submission_id, activity_id, json.dumps(payload), status, sync_status),
        )
    _transaction(work)


def enqueue_sync_event(entity_type, entity_id, operation, payload, event_id=None, user_id=None):
    """Queue one local event for the future local-network sync worker.

    ``user_id`` is the authenticated session user, written by the caller. On an
    idempotent retry the original owner is kept: a conflicting event_id from a
    different account can neither adopt nor overwrite an existing row.
    """
    if not event_id:
        event_id = str(uuid.uuid4())

    def work(connection):
        # status is intentionally NOT overwritten: a queued event stays queued
        # even when the browser retries with the same idempotent event_id.
        connection.execute(
            """INSERT INTO sync_queue (event_id, entity_type, entity_id, operation, payload_json, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                entity_type=excluded.entity_type,
                entity_id=excluded.entity_id,
                operation=excluded.operation,
                payload_json=excluded.payload_json,
                user_id=COALESCE(sync_queue.user_id, excluded.user_id)
            WHERE sync_queue.user_id IS NULL OR sync_queue.user_id = excluded.user_id""",
            (event_id, entity_type, entity_id, operation, json.dumps(payload), user_id),
        )
    _transaction(work)
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