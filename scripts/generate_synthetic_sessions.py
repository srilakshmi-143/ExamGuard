"""Generate clearly marked synthetic sessions for analytics development only."""

import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from database.db_service import DatabaseService

try:
    from faker import Faker
except ImportError as exc:
    raise SystemExit("Install Faker before generating synthetic data: pip install Faker") from exc


def generate(count=12):
    fake = Faker()
    DatabaseService.init_db()
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    exams = [row[0] for row in conn.execute("SELECT id FROM exams WHERE title NOT GLOB '__*'").fetchall()]
    if not exams:
        raise RuntimeError("Create at least one exam first.")
    for _ in range(count):
        marker = uuid.uuid4().hex[:10]
        username = f"synthetic_candidate_{marker}"
        email = f"{username}@synthetic.examguard.local"
        password_hash = generate_password_hash(uuid.uuid4().hex)
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, role, email)
            VALUES (?, ?, 'student', ?)
            """,
            (username, password_hash, email),
        )
        user_id = cursor.lastrowid
        exam_id = random.choice(exams)
        started = datetime.utcnow() - timedelta(days=random.randint(0, 90), minutes=random.randint(0, 120))
        score = random.randint(55, 100)
        status = random.choice(["COMPLETED", "COMPLETED", "TERMINATED"])
        integrity = random.randint(45, 100)
        token = "SYNTHETIC-" + uuid.uuid4().hex
        cursor = conn.execute("""
            INSERT INTO exam_sessions (session_token, user_id, candidate_id, exam_id, status, start_time, end_time, integrity_score, score, percentage, face_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (token, user_id, user_id, exam_id, status, started.strftime("%Y-%m-%d %H:%M:%S"), (started + timedelta(minutes=random.randint(20, 60))).strftime("%Y-%m-%d %H:%M:%S"), integrity, score, score,))
        session_id = cursor.lastrowid
        for event_type in random.sample(["TAB_SWITCH", "FOCUS_LOSS", "FULLSCREEN_EXIT", "NO_FACE_10S", "MULTIPLE_FACES"], random.randint(0, 3)):
            conn.execute("INSERT INTO proctoring_logs (session_id, user_id, exam_id, event_type, severity, details) VALUES (?, ?, ?, ?, ?, ?)", (session_id, user_id, exam_id, event_type, "MEDIUM", "SYNTHETIC_TEST_DATA"))
    conn.commit()
    conn.close()
    print(f"Generated {count} synthetic sessions marked with SYNTHETIC tokens.")


if __name__ == "__main__":
    generate()
