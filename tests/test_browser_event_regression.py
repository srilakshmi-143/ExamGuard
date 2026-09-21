import sqlite3
import unittest
import uuid

from app import app
from database.db_service import DatabaseService
from werkzeug.security import generate_password_hash


class BrowserEventRegressionTests(unittest.TestCase):
    def setUp(self):
        DatabaseService.init_db()
        self.email = f"browser_event_{uuid.uuid4().hex[:12]}@example.com"
        self.other_email = f"browser_other_{uuid.uuid4().hex[:12]}@example.com"
        self.user_id = DatabaseService.create_user(
            f"browser_event_{uuid.uuid4().hex[:8]}",
            generate_password_hash("test-password"),
            "student",
            self.email,
        )
        self.other_user_id = DatabaseService.create_user(
            f"browser_other_{uuid.uuid4().hex[:8]}",
            generate_password_hash("test-password"),
            "student",
            self.other_email,
        )
        with sqlite3.connect(DatabaseService.DB_NAME) as conn:
            self.exam_id = conn.execute(
                "SELECT id FROM exams WHERE title NOT GLOB '__*' ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        self.session_id = DatabaseService.create_exam_session(
            f"BROWSER-{uuid.uuid4().hex}", self.user_id, self.exam_id
        )
        self.other_session_id = DatabaseService.create_exam_session(
            f"BROWSER-{uuid.uuid4().hex}", self.other_user_id, self.exam_id
        )
        self.client = app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session["user_id"] = self.user_id
            flask_session["current_session_id"] = self.session_id
            flask_session["current_exam_session_id"] = self.session_id

    def tearDown(self):
        with sqlite3.connect(DatabaseService.DB_NAME) as conn:
            for table in ("proctoring_logs", "integrity_reports", "suspicious_events"):
                conn.execute(f"DELETE FROM {table} WHERE session_id IN (?, ?)", (self.session_id, self.other_session_id))
            conn.execute("DELETE FROM exam_sessions WHERE id IN (?, ?)", (self.session_id, self.other_session_id))
            conn.execute("DELETE FROM users WHERE id IN (?, ?)", (self.user_id, self.other_user_id))
            conn.commit()

    def test_event_requires_ownership_and_deduplicates_event_id(self):
        first = self.client.post(
            "/api/proctoring/browser-event",
            json={"session_id": self.session_id, "event_type": "COPY", "event_id": "copy-1"},
        )
        duplicate = self.client.post(
            "/api/proctoring/browser-event",
            json={"session_id": self.session_id, "event_type": "COPY", "event_id": "copy-1"},
        )
        cross_owner = self.client.post(
            "/api/proctoring/browser-event",
            json={"session_id": self.other_session_id, "event_type": "PASTE", "event_id": "cross-1"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(cross_owner.status_code, 403)
        with sqlite3.connect(DatabaseService.DB_NAME) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM integrity_reports WHERE session_id = ? AND event_type = 'COPY'",
                    (self.session_id,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT integrity_score FROM exam_sessions WHERE id = ?",
                    (self.session_id,),
                ).fetchone()[0],
                95,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM proctoring_logs WHERE session_id = ? AND event_type = 'PASTE'",
                    (self.other_session_id,),
                ).fetchone()[0],
                0,
            )


if __name__ == "__main__":
    unittest.main()
