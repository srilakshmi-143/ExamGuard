"""
Database Service Module

Handles database initialization, connections, schema creation,
and CRUD operations for users, exams, questions, results,
sessions, logs, and security logs.
"""

import os
import secrets
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config


class DatabaseService:
    DB_NAME = Config.DATABASE_PATH

    @staticmethod
    def _ensure_columns(cursor: sqlite3.Cursor, table: str, columns: Dict[str, str]) -> None:
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cursor.fetchall()}
        for column_name, column_type in columns.items():
            if column_name not in existing:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"
                )

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        """Create and return a database connection with dictionary-like row access."""
        conn = sqlite3.connect(cls.DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        """
        Initialize database tables and create default admin user if not existing.
        Creates:
        - users
        - exams
        - questions
        - options
        - exam_submissions
        - exam_sessions
        - proctoring_logs
        - security_logs
        - active_sessions
        """
        conn = cls.get_connection()
        cursor = conn.cursor()

        # Enable Foreign Key support
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT CHECK(role IN ('admin', 'student')) NOT NULL,
                email TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ============================================================
        # MIGRATE USER PROFILE COLUMNS
        # ============================================================
        cursor.execute("PRAGMA table_info(users)")
        user_columns = {
            row["name"]
            for row in cursor.fetchall()
        }

        # Migrate the original exam.db user schema to the DatabaseService schema.
        if "username" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "password_hash" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

        if "password" in user_columns:
            cursor.execute("""
                UPDATE users
                SET password_hash = password
                WHERE (password_hash IS NULL OR password_hash = '')
                  AND password IS NOT NULL
            """)

        cursor.execute("""
            UPDATE users
            SET username = LOWER(substr(email, 1, instr(email, '@') - 1))
            WHERE (username IS NULL OR username = '')
              AND email IS NOT NULL
        """)
        cursor.execute("""
            UPDATE users
            SET role = 'student'
            WHERE role = 'candidate'
        """)

        profile_columns = {
            "full_name": "TEXT",
            "college": "TEXT",
            "branch": "TEXT",
            "year": "TEXT",
            "roll_number": "TEXT",
            "photo_path": "TEXT",
            "phone": "TEXT",
            "dob": "TEXT",
            "gender": "TEXT"
        }
        DatabaseService._ensure_columns(cursor, "users", profile_columns)

        conn.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                duration INTEGER DEFAULT 60,
                total_marks INTEGER DEFAULT 100,
                status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        DatabaseService._ensure_columns(cursor, "assignments", {
            "total_marks": "INTEGER DEFAULT 100",
            "status": "TEXT DEFAULT 'Pending'",
            "created_at": "TIMESTAMP"
        })

        # Exams Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                duration INTEGER NOT NULL,
                total_marks INTEGER DEFAULT 100,
                pass_percentage REAL DEFAULT 40.0,
                created_by INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
            )
        """)
        DatabaseService._ensure_columns(cursor, "exams", {
            "total_marks": "INTEGER DEFAULT 100",
            "pass_percentage": "REAL DEFAULT 40.0",
            "created_by": "INTEGER",
            "is_active": "INTEGER DEFAULT 1",
            "created_at": "TIMESTAMP"
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                status TEXT DEFAULT 'Pending',
                UNIQUE(user_id, assignment_id)
            )
        """)
        cursor.execute("""
            UPDATE exams
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
        """)

        # Questions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT DEFAULT 'mcq',
                marks INTEGER DEFAULT 1,
                FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
            )
        """)
        DatabaseService._ensure_columns(cursor, "questions", {
            "question_type": "TEXT DEFAULT 'mcq'",
            "marks": "INTEGER DEFAULT 1"
        })

        # Options Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                is_correct INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
            )
        """)

        # Exam Submissions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exam_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exam_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                percentage REAL NOT NULL,
                integrity_score INTEGER NOT NULL,
                violations INTEGER NOT NULL,
                status TEXT DEFAULT 'Completed',
                termination_reason TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
            )
        """)
        DatabaseService._ensure_columns(cursor, "exam_submissions", {
            "session_id": "INTEGER"
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exam_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                selected_option TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, question_id),
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
            )
        """)

        # Exam Sessions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exam_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_token TEXT UNIQUE,
                user_id INTEGER,
                candidate_id INTEGER,
                exam_id INTEGER NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                termination_reason TEXT,
                integrity_score INTEGER DEFAULT 100,
                score INTEGER,
                percentage REAL,
                face_verified INTEGER DEFAULT 0,
                presence_ratio REAL,

                FOREIGN KEY (user_id)
                    REFERENCES users (id)
                    ON DELETE CASCADE,

                FOREIGN KEY (exam_id)
                    REFERENCES exams (id)
                    ON DELETE CASCADE
            )
        """)

        DatabaseService._ensure_columns(cursor, "exam_sessions", {
            "session_token": "TEXT",
            "user_id": "INTEGER",
            "candidate_id": "INTEGER",
            "exam_id": "INTEGER",
            "status": "TEXT DEFAULT 'ACTIVE'",
            "start_time": "TIMESTAMP",
            "end_time": "TIMESTAMP",
            "termination_reason": "TEXT",
            "termination_time": "TIMESTAMP",
            "integrity_score": "INTEGER DEFAULT 100",
            "score": "INTEGER",
            "percentage": "REAL",
            "face_verified": "INTEGER DEFAULT 0",
            "presence_ratio": "REAL",
            "active_started_at": "TIMESTAMP",
            "active_seconds": "INTEGER DEFAULT 0",
            "last_active_at": "TIMESTAMP"
        })

        # Copy old user_id into candidate_id for existing records
        cursor.execute("""
            UPDATE exam_sessions
            SET candidate_id = user_id
            WHERE candidate_id IS NULL
        """)
        conn.commit()

        # Proctoring Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proctoring_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                user_id INTEGER NOT NULL,
                exam_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')) NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
            )
        """)
        DatabaseService._ensure_columns(cursor, "proctoring_logs", {
            "violation_type": "TEXT",
            "event_type": "TEXT",
            "severity": "TEXT",
            "details": "TEXT",
            "timestamp": "TIMESTAMP",
            "event_id": "TEXT"
        })
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_proctoring_event_id ON proctoring_logs(event_id) WHERE event_id IS NOT NULL")

        # Security Logs Table (System/Auth level events)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                description TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """)

        # Active User Sessions Table (Single Session Enforcement)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrity_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                penalty INTEGER NOT NULL,
                score_after INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suspicious_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                event_id INTEGER,
                event_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                description TEXT,
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES proctoring_logs (id) ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_absence_intervals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                absent_start TIMESTAMP NOT NULL,
                absent_end TIMESTAMP,
                duration_seconds REAL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id) ON DELETE CASCADE
            )
        """)

        conn.commit()

        # Remove the historical known default credential if it was created by an
        # earlier version and no replacement bootstrap password is configured.
        bootstrap_password = os.environ.get("EXAMGUARD_BOOTSTRAP_ADMIN_PASSWORD")
        legacy_admin = cursor.execute(
            "SELECT id, password_hash FROM users WHERE username = ? AND email = ?",
            ("admin", "admin@examguard.local")
        ).fetchone()
        if not bootstrap_password and legacy_admin:
            try:
                if check_password_hash(legacy_admin["password_hash"], "admin123"):
                    unusable_hash = generate_password_hash(secrets.token_hex(32))
                    if "password" in user_columns:
                        cursor.execute(
                            "UPDATE users SET password_hash = ?, password = ? WHERE id = ?",
                            (unusable_hash, unusable_hash, legacy_admin["id"])
                        )
                    else:
                        cursor.execute(
                            "UPDATE users SET password_hash = ? WHERE id = ?",
                            (unusable_hash, legacy_admin["id"])
                        )
                    conn.commit()
            except (TypeError, ValueError):
                pass

        # Bootstrap an administrator only when the operator explicitly provides
        # a password. Never create a silently usable default credential.
        cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        if not cursor.fetchone() and bootstrap_password:
            default_admin_user = os.environ.get("EXAMGUARD_BOOTSTRAP_ADMIN_USER", "admin")
            default_admin_email = os.environ.get(
                "EXAMGUARD_BOOTSTRAP_ADMIN_EMAIL",
                "admin@examguard.local"
            )
            default_admin_pass = generate_password_hash(bootstrap_password)
            if "password" in user_columns:
                cursor.execute("""
                    INSERT INTO users (
                        username, password_hash, password, role, email, full_name
                    )
                    VALUES (?, ?, ?, 'admin', ?, ?)
                """, (
                    default_admin_user,
                    default_admin_pass,
                    default_admin_pass,
                    default_admin_email,
                    "Administrator"
                ))
            else:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, email)
                    VALUES (?, ?, 'admin', ?)
                """, (default_admin_user, default_admin_pass, default_admin_email))
            conn.commit()

        conn.close()

    # ==================== USER OPERATIONS ====================

    @staticmethod
    def create_user(username: str, password_hash: str, role: str, email: Optional[str] = None) -> Optional[int]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(users)")
            user_columns = {row["name"] for row in cursor.fetchall()}

            final_email = email or f"{username}@example.com"
            full_name = username

            if "password" in user_columns and "full_name" in user_columns:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, password, role, email, full_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (username, password_hash, password_hash, role, final_email, full_name))
            elif "full_name" in user_columns:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, email, full_name)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, password_hash, role, final_email, full_name))
            elif "password" in user_columns:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, password, role, email)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, password_hash, password_hash, role, final_email))
            else:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, email)
                    VALUES (?, ?, ?, ?)
                """, (username, password_hash, role, final_email))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            return None
        finally:
            conn.close()

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT * FROM users WHERE id = ? LIMIT 1",
                (user_id,)
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

        finally:
            conn.close()

    @staticmethod
    def get_candidate_profile(user_id: int) -> Optional[Dict[str, Any]]:
        """Return the candidate profile stored on the users row."""
        return DatabaseService.get_user_by_id(user_id)

    @staticmethod
    def get_user_assignment_history(user_id: int) -> List[Dict[str, Any]]:
        """Return the candidate's submissions and current exam sessions."""
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    es.id AS session_id,
                    es.exam_id,
                    e.title AS exam_title,
                    COALESCE(es.status, 'ACTIVE') AS status,
                    es.score,
                    es.percentage,
                    es.integrity_score,
                    es.start_time,
                    es.end_time,
                    es.termination_reason
                FROM exam_sessions es
                JOIN exams e ON e.id = es.exam_id
                WHERE es.candidate_id = ? OR es.user_id = ?
                ORDER BY es.id DESC
            """, (user_id, user_id))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT *
                FROM users
                WHERE LOWER(email) = LOWER(?)
                LIMIT 1
            """, (email.strip(),))

            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

        finally:
            conn.close()

    @staticmethod
    def create_candidate_with_profile(
        username: str,
        email: str,
        password: str,
        full_name: str,
        college: str = "",
        branch: str = "",
        year: str = "",
        roll_number: str = "",
        photo_path: Optional[str] = None
    ) -> Optional[int]:

        DatabaseService.init_db()

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            # Check whether email already exists
            cursor.execute("""
                SELECT id
                FROM users
                WHERE LOWER(email) = LOWER(?)
                LIMIT 1
            """, (email.strip(),))

            existing = cursor.fetchone()

            if existing:
                print("Registration failed: email already exists.")
                return None

            # Create candidate account
            password_hash = generate_password_hash(password)
            cursor.execute("PRAGMA table_info(users)")
            user_columns = {row["name"] for row in cursor.fetchall()}

            if "password" in user_columns:
                cursor.execute("""
                    INSERT INTO users (
                        username, password_hash, password, role, email,
                        full_name, college, branch, year, roll_number, photo_path
                    )
                    VALUES (?, ?, ?, 'student', ?, ?, ?, ?, ?, ?, ?)
                """, (
                    username,
                    password_hash,
                    password_hash,
                    email.strip(),
                    full_name,
                    college,
                    branch,
                    year,
                    roll_number,
                    photo_path
                ))
            else:
                cursor.execute("""
                    INSERT INTO users (
                        username, password_hash, role, email,
                        full_name, college, branch, year, roll_number, photo_path
                    )
                    VALUES (?, ?, 'student', ?, ?, ?, ?, ?, ?, ?)
                """, (
                    username,
                    password_hash,
                    email.strip(),
                    full_name,
                    college,
                    branch,
                    year,
                    roll_number,
                    photo_path
                ))

            user_id = cursor.lastrowid

            conn.commit()

            print("Candidate registered successfully:", user_id)

            return user_id

        except sqlite3.IntegrityError as e:
            conn.rollback()
            print("Registration database error:", e)
            return None

        except Exception as e:
            conn.rollback()
            print("Registration error:", e)
            return None

        finally:
            conn.close()

    @staticmethod
    def get_all_users() -> List[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, email, created_at FROM users ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ==================== EXAM OPERATIONS ====================

    @staticmethod
    def create_exam(title: str, description: str, duration: int, total_marks: int, pass_percentage: float, created_by: int) -> int:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exams (title, description, duration, total_marks, pass_percentage, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, description, duration, total_marks, pass_percentage, created_by))
        conn.commit()
        exam_id = cursor.lastrowid
        conn.close()
        return exam_id

    @staticmethod
    def get_all_exams(active_only: bool = True) -> List[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM exams WHERE is_active = 1 ORDER BY id DESC")
        else:
            cursor.execute("SELECT * FROM exams ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_exam_by_id(exam_id: int) -> Optional[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_assignment_by_id(assignment_id: int):
        """
        Assignment compatibility method.
        In the current project, an assignment is an exam.
        """

        DatabaseService.init_db()

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    id,
                    title,
                    description,
                    duration,
                    duration AS duration_minutes,
                    total_marks,
                    pass_percentage,
                    created_by,
                    is_active,
                    created_at
                FROM exams
                WHERE id = ?
                LIMIT 1
            """, (assignment_id,))

            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

        finally:
            conn.close()

    @staticmethod
    def toggle_exam_status(exam_id: int, is_active: int) -> bool:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE exams SET is_active = ? WHERE id = ?", (is_active, exam_id))
        conn.commit()
        affected = cursor.rowcount > 0
        conn.close()
        return affected

    @staticmethod
    def delete_exam(exam_id: int) -> bool:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
        conn.commit()
        affected = cursor.rowcount > 0
        conn.close()
        return affected

    # ==================== QUESTION & OPTION OPERATIONS ====================

    @staticmethod
    def add_question(exam_id: int, question_text: str, question_type: str, marks: int, options: List[Dict[str, Any]]) -> int:
        """
        Adds a question and its associated options.
        `options` is a list of dicts: [{"text": "Option A", "is_correct": 1}, ...]
        """
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("PRAGMA table_info(questions)")
            question_columns = {row["name"] for row in cursor.fetchall()}

            if {"option_a", "option_b", "option_c", "option_d", "correct_option"}.issubset(question_columns):
                option_values = [str(option.get("text", "")) for option in options]
                option_values += [""] * (4 - len(option_values))
                correct_index = next(
                    (index for index, option in enumerate(options) if option.get("is_correct")),
                    0
                )
                cursor.execute("""
                    INSERT INTO questions (
                        exam_id, question_text, question_type, marks,
                        option_a, option_b, option_c, option_d, correct_option
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    exam_id,
                    question_text,
                    question_type,
                    marks,
                    option_values[0],
                    option_values[1],
                    option_values[2],
                    option_values[3],
                    chr(65 + correct_index)
                ))
            else:
                cursor.execute("""
                    INSERT INTO questions (exam_id, question_text, question_type, marks)
                    VALUES (?, ?, ?, ?)
                """, (exam_id, question_text, question_type, marks))
            question_id = cursor.lastrowid

            for opt in options:
                cursor.execute("""
                    INSERT INTO options (question_id, option_text, is_correct)
                    VALUES (?, ?, ?)
                """, (question_id, opt['text'], opt.get('is_correct', 0)))

            conn.commit()
            return question_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def seed_default_questions_for_exam(exam_id: int) -> List[Dict[str, Any]]:
        """Ensure a candidate-visible exam has a working MCQ question bank."""
        exam = DatabaseService.get_exam_by_id(exam_id)
        if not exam:
            return []

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS question_count FROM questions WHERE exam_id = ?", (exam_id,))
        row = cursor.fetchone()
        count = int((row["question_count"] if row and row["question_count"] is not None else 0) or 0)
        conn.close()

        if count > 0:
            return DatabaseService.get_questions_for_exam(exam_id)

        title = str(exam.get("title") or "").lower()
        generic_questions = [
            ("Which of the following is a valid Python data type for key-value storage?", ["List", "Tuple", "Dictionary", "Set"], 2),
            ("Which keyword defines a function in Python?", ["function", "def", "func", "define"], 1),
            ("Which SQL clause filters rows?", ["ORDER BY", "WHERE", "GROUP BY", "LIMIT"], 1),
            ("Which HTTP status code indicates a resource was not found?", ["200", "301", "404", "500"], 2),
            ("Which data structure follows FIFO order?", ["Stack", "Queue", "Tree", "Graph"], 1),
            ("What does HTML primarily define?", ["Database schema", "Page structure", "Operating system", "Compiler output"], 1),
            ("Which library is commonly used for numerical arrays in Python?", ["NumPy", "Flask", "Jinja", "SQLite"], 0),
            ("What is the purpose of a primary key in a database?", ["To format output", "To uniquely identify a row", "To encrypt data", "To sort columns"], 1),
            ("Which of the following is a common machine learning task?", ["Image classification", "File deletion", "Memory formatting", "CSS styling"], 0),
            ("What is the goal of monitoring in an exam platform?", ["To hide content", "To detect suspicious behaviour", "To reduce internet speed", "To delete sessions"], 1),
        ]

        if "python" in title:
            generic_questions = [
                ("Which keyword creates a class in Python?", ["class", "type", "struct", "object"], 0),
                ("Which collection stores unique values?", ["List", "Tuple", "Set", "Queue"], 2),
                ("Which data type is immutable?", ["List", "Dictionary", "Tuple", "Set"], 2),
                ("What does len() return?", ["A string", "An integer", "A float", "A boolean"], 1),
                ("Which keyword defines a function?", ["function", "def", "func", "define"], 1),
                ("Which operator checks equality in Python?", ["=", "==", "!=", "< >"], 1),
                ("Which construct is used for iteration over a sequence?", ["for loop", "if statement", "switch", "print"], 0),
                ("What does a dictionary hold?", ["Indexed values only", "Key-value pairs", "Only strings", "Only integers"], 1),
                ("Which method converts a string to lowercase?", ["lower()", "upper()", "strip()", "split()"], 0),
                ("What is a module in Python?", ["A class", "A reusable file of code", "A database", "A browser"], 1),
            ]
        elif "flask" in title or "web" in title:
            generic_questions = [
                ("Which Flask object handles incoming requests?", ["request", "session", "url_for", "flash"], 0),
                ("Which SQL clause filters rows?", ["ORDER BY", "WHERE", "GROUP BY", "LIMIT"], 1),
                ("Which HTTP status means not found?", ["200", "301", "404", "500"], 2),
                ("Which method sends JSON in Flask?", ["jsonify", "render", "redirect", "flash"], 0),
                ("Which SQL command adds a row?", ["SELECT", "INSERT", "UPDATE", "ALTER"], 1),
                ("What is the purpose of a route in Flask?", ["To define a URL endpoint", "To style CSS", "To open a database", "To compile code"], 0),
                ("Which HTML element is used for a form input?", ["<table>", "<input>", "<img>", "<div>"], 1),
                ("Which Python file is commonly used for app configuration?", ["config.py", "README.md", "requirements.txt", "app.css"], 0),
                ("What does SQL stand for?", ["Simple Query Language", "Structured Query Language", "System Query Logic", "Standard Query List"], 1),
                ("Which directive returns a rendered template in Flask?", ["render_template", "redirect", "send_file", "jsonify"], 0),
            ]
        elif "ai" in title or "machine" in title or "ml" in title:
            generic_questions = [
                ("What does AI stand for?", ["Automated Input", "Artificial Intelligence", "Applied Internet", "Advanced Indexing"], 1),
                ("Which library is used for numerical arrays?", ["NumPy", "Flask", "Jinja", "SQLite"], 0),
                ("What does a classifier predict?", ["Labels", "Ports", "URLs", "Schemas"], 0),
                ("Which metric measures classification correctness?", ["Accuracy", "Latency", "Memory", "Depth"], 0),
                ("What is clustering?", ["Grouping similar data", "Encrypting data", "Sorting files", "Serving HTML"], 0),
                ("Which technique is used to detect patterns in data?", ["Machine learning", "SQL querying", "HTML parsing", "Image compression"], 0),
                ("A model is trained to improve by minimizing what?", ["Loss", "Noise", "Color", "File size"], 0),
                ("Which of these is a common supervised learning task?", ["Classification", "Scrolling", "Routing", "Seeding"], 0),
                ("What is feature extraction?", ["Selecting model input variables", "Removing files", "Editing CSS", "Compressing bytes"], 0),
                ("Why is validation data used?", ["To tune and check model performance", "To delete the dataset", "To increase latency", "To generate HTML"], 0),
            ]

        for question_text, options, correct_index in generic_questions:
            DatabaseService.add_question(
                exam_id,
                question_text,
                "mcq",
                1,
                [{"text": value, "is_correct": int(index == correct_index)} for index, value in enumerate(options)]
            )

        return DatabaseService.get_questions_for_exam(exam_id)

    @staticmethod
    def get_questions_for_exam(exam_id: int, include_correct: bool = False) -> List[Dict[str, Any]]:
        """Fetch all questions and their options for a given exam."""
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS question_count FROM questions WHERE exam_id = ?", (exam_id,))
        row = cursor.fetchone()
        count = int((row["question_count"] if row and row["question_count"] is not None else 0) or 0)
        conn.close()

        if count == 0:
            DatabaseService.seed_default_questions_for_exam(exam_id)

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY id ASC", (exam_id,))
        questions = [dict(q) for q in cursor.fetchall()]

        for q in questions:
            if include_correct:
                cursor.execute("SELECT id, option_text, is_correct FROM options WHERE question_id = ?", (q['id'],))
            else:
                cursor.execute("SELECT id, option_text FROM options WHERE question_id = ?", (q['id'],))

            option_rows = [dict(opt) for opt in cursor.fetchall()]
            if option_rows:
                q['options'] = {
                    chr(65 + index): option['option_text']
                    for index, option in enumerate(option_rows)
                }
                if include_correct:
                    for index, option in enumerate(option_rows):
                        if option.get('is_correct'):
                            q['correct_option'] = chr(65 + index)
                            break
            else:
                q['options'] = {
                    letter: q[column]
                    for letter, column in zip(
                        ('A', 'B', 'C', 'D'),
                        ('option_a', 'option_b', 'option_c', 'option_d')
                    )
                    if q.get(column) is not None
                }
            q['question'] = q.get('question_text', q.get('question', ''))

        conn.close()
        return questions

    @staticmethod
    def get_exam_questions(
        exam_id: int,
        include_correct: bool = False
    ) -> List[Dict[str, Any]]:
        """Compatibility alias for get_questions_for_exam()."""

        return DatabaseService.get_questions_for_exam(
            exam_id,
            include_correct
        )

    @staticmethod
    def get_session_by_token(session_token: str) -> Optional[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            row = conn.execute("""
                SELECT * FROM exam_sessions
                WHERE session_token = ?
                LIMIT 1
            """, (session_token,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ==================== PROCTORING & SESSION OPERATIONS ====================

    @staticmethod
    def start_exam_session(user_id: int, exam_id: int) -> int:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exam_sessions (user_id, candidate_id, exam_id, status)
            VALUES (?, ?, ?, 'ACTIVE')
        """, (user_id, user_id, exam_id))
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        return session_id

    @staticmethod
    def create_exam_session(
        session_token: str,
        candidate_id: int,
        exam_id: int
    ) -> Optional[int]:

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            print("\n========== CREATE EXAM SESSION ==========")
            print("session_token:", session_token)
            print("candidate_id:", candidate_id)
            print("exam_id:", exam_id)

            # Check user
            cursor.execute(
                "SELECT id FROM users WHERE id = ?",
                (candidate_id,)
            )

            user = cursor.fetchone()

            if user is None:
                print("ERROR: User does not exist:", candidate_id)
                return None

            # Check exam
            cursor.execute(
                "SELECT id FROM exams WHERE id = ?",
                (exam_id,)
            )

            exam = cursor.fetchone()

            if exam is None:
                print("ERROR: Exam does not exist:", exam_id)
                return None

            # Check whether this token already exists
            cursor.execute(
                """
                SELECT id
                FROM exam_sessions
                WHERE session_token = ?
                """,
                (session_token,)
            )

            existing_session = cursor.fetchone()

            if existing_session:
                print(
                    "Existing session found:",
                    existing_session["id"]
                )

                return existing_session["id"]

            active_session = cursor.execute(
                """
                SELECT id
                FROM exam_sessions
                WHERE candidate_id = ? AND exam_id = ? AND status = 'ACTIVE'
                ORDER BY id DESC
                LIMIT 1
                """,
                (candidate_id, exam_id)
            ).fetchone()
            if active_session:
                print("Active session already exists:", active_session["id"])
                return active_session["id"]

            # Create new session
            cursor.execute(
                """
                INSERT INTO exam_sessions
                (
                    session_token,
                    user_id,
                    candidate_id,
                    exam_id,
                    status,
                    start_time,
                    integrity_score,
                    face_verified
                )
                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?,
                    'ACTIVE',
                    CURRENT_TIMESTAMP,
                    100,
                    0
                )
                """,
                (
                    session_token,
                    candidate_id,
                    candidate_id,
                    exam_id
                )
            )

            session_id = cursor.lastrowid

            conn.commit()

            print(
                "SUCCESS - Exam session created:",
                session_id
            )

            print("========================================\n")

            return session_id

        except Exception as e:

            conn.rollback()

            print(
                "\nERROR creating examination session:",
                repr(e)
            )

            import traceback
            traceback.print_exc()

            print("========================================\n")

            return None

        finally:
            conn.close()

    @staticmethod
    def get_exam_session(session_id: int) -> Optional[Dict[str, Any]]:
        """Get one examination session by ID."""
        DatabaseService.init_db()

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT *
                FROM exam_sessions
                WHERE id = ?
                LIMIT 1
            """, (session_id,))

            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

        finally:
            conn.close()

    @staticmethod
    def mark_face_verified(session_id: int, verified: bool = True) -> bool:

        DatabaseService.init_db()

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                UPDATE exam_sessions
                SET face_verified = ?
                WHERE id = ? AND status = 'ACTIVE'
            """, (
                1 if verified else 0,
                session_id
            ))

            conn.commit()

            return cursor.rowcount > 0

        finally:
            conn.close()

    @staticmethod
    def activate_exam_session(session_id: int) -> Optional[Dict[str, Any]]:
        """Start the authoritative exam clock after identity verification."""
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            conn.execute("""
                UPDATE exam_sessions
                SET active_started_at = COALESCE(active_started_at, CURRENT_TIMESTAMP),
                    last_active_at = COALESCE(last_active_at, CURRENT_TIMESTAMP),
                    active_seconds = COALESCE(active_seconds, 0)
                WHERE id = ? AND status = 'ACTIVE' AND face_verified = 1
            """, (session_id,))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM exam_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def update_active_time(session_id: int, resume: bool = False) -> Optional[Dict[str, Any]]:
        """Advance active time only across a normal heartbeat interval.

        A resume heartbeat deliberately resets the baseline so an outage gap is
        never charged to the candidate.
        """
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM exam_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            if not row:
                return None
            if resume:
                conn.execute(
                    "UPDATE exam_sessions SET last_active_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (session_id,)
                )
            elif row["status"] == "ACTIVE" and row["active_started_at"]:
                conn.execute("""
                    UPDATE exam_sessions
                    SET active_seconds = COALESCE(active_seconds, 0) +
                        MIN(5, MAX(0, CAST((julianday('now') - julianday(last_active_at)) * 86400 AS INTEGER))),
                        last_active_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'ACTIVE' AND last_active_at IS NOT NULL
                """, (session_id,))
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM exam_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            return dict(updated) if updated else None
        finally:
            conn.close()

    @staticmethod
    def get_integrity_score(session_id: int) -> int:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            row = conn.execute(
                "SELECT integrity_score FROM exam_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            return int(row["integrity_score"] if row and row["integrity_score"] is not None else 100)
        finally:
            conn.close()

    @staticmethod
    def get_tab_switch_count(session_id: int) -> int:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            row = conn.execute("""
                SELECT COUNT(*) AS count
                FROM proctoring_logs
                WHERE session_id = ?
                  AND (event_type = 'TAB_SWITCH' OR violation_type = 'TAB_SWITCH')
            """, (session_id,)).fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()

    @staticmethod
    def get_violation_count(session_id: int, event_type: str) -> int:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            from services.integrity_engine import IntegrityEngine
            aliases = IntegrityEngine.event_aliases(event_type)
            placeholders = ",".join("?" for _ in aliases)
            row = conn.execute(f"""
                SELECT COUNT(*) AS count
                FROM proctoring_logs
                WHERE session_id = ?
                  AND (event_type IN ({placeholders}) OR violation_type IN ({placeholders}))
            """, (session_id, *aliases, *aliases)).fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()

    @staticmethod
    def get_integrity_event_count(session_id: int, event_type: str) -> int:
        """Count one persisted integrity decision per event type."""
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            row = conn.execute("""
                SELECT COUNT(*) AS count
                FROM integrity_reports
                WHERE session_id = ? AND event_type = ?
            """, (session_id, event_type)).fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()

    @staticmethod
    def get_total_violation_count(session_id: int) -> int:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            row = conn.execute("""
                SELECT COUNT(*) AS count
                FROM integrity_reports
                WHERE session_id = ?
            """, (session_id,)).fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()

    @staticmethod
    def log_browser_event(session_id: int, event_type: str, details: str = "", event_id: Optional[str] = None) -> None:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            from services.integrity_engine import IntegrityEngine
            event_type = IntegrityEngine.normalize_event_type(event_type)
            if event_id and conn.execute("SELECT 1 FROM proctoring_logs WHERE event_id = ?", (event_id,)).fetchone():
                return
            session_row = conn.execute("""
                SELECT user_id, exam_id FROM exam_sessions WHERE id = ?
            """, (session_id,)).fetchone()
            if not session_row:
                return
            conn.execute("""
                INSERT INTO proctoring_logs
                    (session_id, user_id, exam_id, event_type, severity, details, timestamp, event_id)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (
                session_id,
                session_row["user_id"],
                session_row["exam_id"],
                event_type,
                "MEDIUM",
                details,
                event_id
            ))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def log_suspicious_event(
        session_id: int,
        event_type: str,
        severity: str,
        description: str,
        deduction: int,
        event_id: Optional[str] = None
    ) -> int:
        from services.integrity_engine import IntegrityEngine
        event_type = IntegrityEngine.normalize_event_type(event_type)
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            if event_id and conn.execute("SELECT 1 FROM proctoring_logs WHERE event_id = ?", (event_id,)).fetchone():
                return DatabaseService.get_integrity_score(session_id)
            current = DatabaseService.get_integrity_score(session_id)
            new_score = max(0, current - int(deduction or 0))
            conn.execute("""
                UPDATE exam_sessions SET integrity_score = ? WHERE id = ?
            """, (new_score, session_id))
            conn.execute("""
                INSERT INTO integrity_reports
                    (session_id, event_type, penalty, score_after)
                VALUES (?, ?, ?, ?)
            """, (session_id, event_type, deduction, new_score))
            conn.execute("""
                INSERT INTO suspicious_events (session_id, event_type, details)
                VALUES (?, ?, ?)
            """, (session_id, event_type, description))
            session_row = conn.execute("""
                SELECT user_id, exam_id FROM exam_sessions WHERE id = ?
            """, (session_id,)).fetchone()
            if session_row:
                conn.execute("""
                    INSERT INTO proctoring_logs
                        (session_id, user_id, exam_id, event_type, severity, details, timestamp, event_id)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (
                    session_id,
                    session_row["user_id"],
                    session_row["exam_id"],
                    event_type,
                    severity,
                    description,
                    event_id
                ))
            conn.commit()
            return new_score
        finally:
            conn.close()

    @staticmethod
    def update_session_status(session_id: int, status: str, reason: Optional[str] = None):
        """Updates session status cleanly using named parameters to guarantee accurate binding."""
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE exam_sessions
                SET
                    status = :status,
                    termination_reason = COALESCE(:reason, termination_reason),
                    end_time = CASE
                        WHEN :status IN ('COMPLETED', 'TERMINATED') THEN CURRENT_TIMESTAMP
                        ELSE end_time
                    END,
                    termination_time = CASE
                        WHEN :status = 'TERMINATED' THEN CURRENT_TIMESTAMP
                        ELSE termination_time
                    END
                WHERE id = :session_id
            """, {
                "status": status,
                "reason": reason,
                "session_id": session_id
            })
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def save_presence_ratio(session_id: int, presence_ratio: Optional[float]) -> None:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            conn.execute(
                "UPDATE exam_sessions SET presence_ratio = ? WHERE id = ?",
                (presence_ratio, session_id),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def save_exam_session_result(
        session_id: int,
        score: int,
        percentage: float,
        integrity_score: int,
        status: str = "COMPLETED"
    ) -> None:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            conn.execute("""
                UPDATE exam_sessions
                SET score = ?, percentage = ?, integrity_score = ?, status = ?,
                    end_time = CASE
                        WHEN ? IN ('COMPLETED', 'TERMINATED') THEN CURRENT_TIMESTAMP
                        ELSE end_time
                    END,
                    termination_time = CASE
                        WHEN ? = 'TERMINATED' THEN CURRENT_TIMESTAMP
                        ELSE termination_time
                    END
                WHERE id = ?
            """, (
                score,
                percentage,
                integrity_score,
                status,
                status,
                status,
                session_id
            ))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def log_proctoring_event(session_id: Optional[int], user_id: int, exam_id: int, event_type: str, severity: str, details: str = ""):
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO proctoring_logs (session_id, user_id, exam_id, event_type, severity, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, user_id, exam_id, event_type, severity, details))
        conn.commit()
        conn.close()

    @staticmethod
    def get_proctoring_logs_for_session(session_id: int) -> List[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM proctoring_logs WHERE session_id = ? ORDER BY timestamp ASC
        """, (session_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ==================== SECURITY & SINGLE SESSION OPERATIONS ====================

    @staticmethod
    def set_active_session(user_id: int, session_token: str):
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO active_sessions (user_id, session_token, login_time, last_activity)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                session_token = excluded.session_token,
                login_time = CURRENT_TIMESTAMP,
                last_activity = CURRENT_TIMESTAMP
        """, (user_id, session_token))
        conn.commit()
        conn.close()

    @staticmethod
    def validate_active_session(user_id: int, session_token: str) -> bool:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_token FROM active_sessions WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()

        if row and row['session_token'] == session_token:
            cursor.execute("""
                UPDATE active_sessions SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            conn.close()
            return True

        conn.close()
        return False

    @staticmethod
    def clear_active_session(user_id: int):
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def log_security_event(user_id: Optional[int], event_type: str, description: str, ip_address: Optional[str] = None):
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO security_logs (user_id, event_type, description, ip_address)
            VALUES (?, ?, ?, ?)
        """, (user_id, event_type, description, ip_address))
        conn.commit()
        conn.close()

    @staticmethod
    def get_security_logs(limit: int = 100) -> List[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sl.*, u.username 
            FROM security_logs sl
            LEFT JOIN users u ON sl.user_id = u.id
            ORDER BY sl.timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ==================== SUBMISSION & RESULT OPERATIONS ====================

    @staticmethod
    def save_exam_submission(
        user_id: int,
        exam_id: int,
        score: int,
        total: int,
        percentage: float,
        integrity_score: int,
        violations: int,
        status: str = "Completed",
        termination_reason: Optional[str] = None,
        session_id: Optional[int] = None
    ):
        """Saves or updates an exam submission while validating state integrity."""
        DatabaseService.init_db()

        conn = DatabaseService.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT id, status
                FROM exam_submissions
                WHERE user_id = ?
                  AND exam_id = ?
                ORDER BY id DESC
                LIMIT 1
            """, (user_id, exam_id))

            existing = cursor.fetchone()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            existing_status = str(existing["status"] or "").strip().lower() if existing else ""

            if existing and existing_status != "terminated":

                if existing_status in ("completed", "submitted"):
                    raise ValueError(
                        "This examination has already been completed."
                    )

                cursor.execute("""
                    UPDATE exam_submissions
                    SET
                        score = ?,
                        total = ?,
                        percentage = ?,
                        integrity_score = ?,
                        violations = ?,
                        status = ?,
                        termination_reason = ?,
                        session_id = ?,
                        completed_at = ?
                    WHERE id = ?
                """, (
                    score,
                    total,
                    percentage,
                    integrity_score,
                    violations,
                    status,
                    termination_reason,
                    session_id,
                    now,
                    existing["id"]
                ))
            else:
                cursor.execute("""
                    INSERT INTO exam_submissions
                    (
                        user_id,
                        exam_id,
                        session_id,
                        score,
                        total,
                        percentage,
                        integrity_score,
                        violations,
                        status,
                        termination_reason,
                        completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    exam_id,
                    session_id,
                    score,
                    total,
                    percentage,
                    integrity_score,
                    violations,
                    status,
                    termination_reason,
                    now
                ))

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    @staticmethod
    def save_exam_answers(session_id: int, answers: Dict[str, Any]) -> None:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            for question_id, selected_option in answers.items():
                if not str(question_id).isdigit():
                    continue
                conn.execute("""
                    INSERT INTO exam_answers (session_id, question_id, selected_option)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id, question_id)
                    DO UPDATE SET selected_option = excluded.selected_option
                """, (session_id, int(question_id), str(selected_option or "")))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_exam_answers(session_id: int) -> Dict[int, str]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        try:
            rows = conn.execute("""
                SELECT question_id, selected_option
                FROM exam_answers
                WHERE session_id = ?
            """, (session_id,)).fetchall()
            return {int(row["question_id"]): row["selected_option"] or "" for row in rows}
        finally:
            conn.close()

    @staticmethod
    def get_user_submissions(user_id: int) -> List[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sub.*, e.title as exam_title, e.duration,
                     es.start_time, es.end_time, es.presence_ratio,
                   (SELECT COUNT(*) FROM proctoring_logs pl WHERE pl.session_id = sub.session_id AND (pl.event_type = 'TAB_SWITCH' OR pl.violation_type = 'TAB_SWITCH')) AS tab_switches,
                   (SELECT COUNT(*) FROM proctoring_logs pl WHERE pl.session_id = sub.session_id AND (pl.event_type IN ('FACE_ABSENT', 'NO_FACE', 'NO_FACE_WARNING', 'NO_FACE_10S') OR pl.violation_type IN ('FACE_ABSENT', 'NO_FACE', 'NO_FACE_WARNING', 'NO_FACE_10S'))) AS face_missing,
                   (SELECT COUNT(*) FROM proctoring_logs pl WHERE pl.session_id = sub.session_id AND (pl.event_type IN ('MULTIPLE_FACE', 'MULTIPLE_FACES') OR pl.violation_type IN ('MULTIPLE_FACE', 'MULTIPLE_FACES'))) AS multiple_faces,
                   (SELECT COUNT(*) FROM proctoring_logs pl WHERE pl.session_id = sub.session_id AND (pl.event_type = 'FULLSCREEN_EXIT' OR pl.violation_type = 'FULLSCREEN_EXIT')) AS fullscreen_exits,
                   (SELECT COUNT(*) FROM proctoring_logs pl WHERE pl.session_id = sub.session_id AND (pl.event_type = 'PHONE_DETECTED' OR pl.violation_type = 'PHONE_DETECTED')) AS phone_violations
            FROM exam_submissions sub
            JOIN exams e ON sub.exam_id = e.id
            LEFT JOIN exam_sessions es ON es.id = sub.session_id
            WHERE sub.user_id = ?
            ORDER BY sub.completed_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        records = [dict(row) for row in rows]
        attempt_counts: Dict[int, int] = {}
        for record in reversed(records):
            exam_id = int(record["exam_id"])
            attempt_counts[exam_id] = attempt_counts.get(exam_id, 0) + 1
            record["attempt_number"] = attempt_counts[exam_id]
        return records

    @staticmethod
    def get_all_submissions() -> List[Dict[str, Any]]:
        DatabaseService.init_db()
        conn = DatabaseService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sub.*, u.username, e.title as exam_title
            FROM exam_submissions sub
            JOIN users u ON sub.user_id = u.id
            JOIN exams e ON sub.exam_id = e.id
            ORDER BY sub.completed_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        records = [dict(row) for row in rows]
        attempt_counts: Dict[int, int] = {}
        for record in reversed(records):
            exam_id = int(record["exam_id"])
            attempt_counts[exam_id] = attempt_counts.get(exam_id, 0) + 1
            record["attempt_number"] = attempt_counts[exam_id]
        return records