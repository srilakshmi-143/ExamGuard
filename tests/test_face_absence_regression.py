import time
import unittest
import uuid

from database.db_service import DatabaseService
from services import decision_engine
from services.decision_engine import DecisionEngine


class FaceAbsenceRegressionTests(unittest.TestCase):
    def setUp(self):
        DatabaseService.init_db()
        self.seed = int(time.time() * 1000)
        self.username = f"face_absence_user_{self.seed}_{uuid.uuid4().hex[:8]}"
        self.email = f"face_absence_{uuid.uuid4().hex[:12]}@example.com"
        self.session_token = f"REG-SESSION-{uuid.uuid4().hex[:16]}"

        self.user_id = DatabaseService.create_user(
            self.username,
            "hash",
            "student",
            self.email
        )
        self.assertIsNotNone(self.user_id, "User creation failed; stale DB state is interfering with the test.")

        self.exam_id = DatabaseService.create_exam(
            f"Face Absence Regression {uuid.uuid4().hex[:8]}",
            "Regression check for face absence scoring.",
            30,
            100,
            40.0,
            self.user_id
        )
        self.assertIsNotNone(self.exam_id, "Exam creation failed.")

        self.session_id = DatabaseService.create_exam_session(
            self.session_token,
            self.user_id,
            self.exam_id
        )
        self.assertIsNotNone(self.session_id, "Session creation failed.")

        conn = DatabaseService.get_connection()
        conn.execute(
            "UPDATE exam_sessions SET status = 'ACTIVE', integrity_score = 100 WHERE id = ?",
            (self.session_id,)
        )
        conn.commit()
        conn.close()

        decision_engine.NO_FACE_TIMERS.pop(self.session_id, None)
        decision_engine.FACE_ABSENT_CONFIRMED.discard(self.session_id)
        decision_engine.FACE_ABSENT_TERMINATED.discard(self.session_id)

    def tearDown(self):
        try:
            conn = DatabaseService.get_connection()
            conn.execute("DELETE FROM proctoring_logs WHERE session_id = ?", (self.session_id,))
            conn.execute("DELETE FROM integrity_reports WHERE session_id = ?", (self.session_id,))
            conn.execute("DELETE FROM suspicious_events WHERE session_id = ?", (self.session_id,))
            conn.execute("DELETE FROM face_absence_intervals WHERE session_id = ?", (self.session_id,))
            conn.execute("DELETE FROM exam_sessions WHERE id = ?", (self.session_id,))
            if self.exam_id is not None:
                conn.execute("DELETE FROM exams WHERE id = ?", (self.exam_id,))
            if self.user_id is not None:
                conn.execute("DELETE FROM users WHERE id = ?", (self.user_id,))
            conn.commit()
        finally:
            conn.close()

        decision_engine.NO_FACE_TIMERS.pop(self.session_id, None)
        decision_engine.FACE_ABSENT_CONFIRMED.discard(self.session_id)
        decision_engine.FACE_ABSENT_TERMINATED.discard(self.session_id)

    def test_face_absence_applies_one_penalty_at_threshold(self):
        conn = DatabaseService.get_connection()
        try:
            decision_engine.NO_FACE_TIMERS[self.session_id] = time.time() - 3

            response = DecisionEngine.evaluate_frame(conn, self.session_id, 0, 'NO_FACE', False)
            self.assertEqual(response['action'], 'WARNING')
            self.assertIn('missing_seconds', response)
            self.assertEqual(DatabaseService.get_integrity_score(self.session_id), 90)

            decision_engine.NO_FACE_TIMERS[self.session_id] = time.time() - 5
            second = DecisionEngine.evaluate_frame(conn, self.session_id, 0, 'NO_FACE', False)
            self.assertEqual(second['action'], 'WARNING')
            self.assertEqual(DatabaseService.get_integrity_score(self.session_id), 90)
        finally:
            conn.close()

    def test_termination_persists_reason_and_score(self):
        conn = DatabaseService.get_connection()
        try:
            decision_engine.NO_FACE_TIMERS[self.session_id] = time.time() - 3
            first = DecisionEngine.evaluate_frame(conn, self.session_id, 0, 'NO_FACE', False)
            self.assertEqual(first['action'], 'WARNING')

            decision_engine.NO_FACE_TIMERS[self.session_id] = time.time() - 12
            decision_engine.FACE_ABSENT_CONFIRMED.add(self.session_id)
            terminal = DecisionEngine.evaluate_frame(conn, self.session_id, 0, 'NO_FACE', False)
            self.assertEqual(terminal['action'], 'TERMINATE')
            self.assertIn('Candidate face missing continuously', terminal['reason'])

            DatabaseService.update_session_status(
                self.session_id,
                'TERMINATED',
                terminal['reason']
            )
            DatabaseService.save_exam_submission(
                user_id=self.user_id,
                exam_id=self.exam_id,
                session_id=self.session_id,
                score=0,
                total=100,
                percentage=0.0,
                integrity_score=DatabaseService.get_integrity_score(self.session_id),
                violations=DatabaseService.get_total_violation_count(self.session_id),
                status='TERMINATED',
                termination_reason=terminal['reason']
            )

            session = DatabaseService.get_exam_session(self.session_id)
            self.assertEqual(session['status'], 'TERMINATED')
            self.assertIn('Candidate face missing continuously', session['termination_reason'])
            self.assertIsNotNone(session['termination_time'])
            self.assertEqual(session['integrity_score'], DatabaseService.get_integrity_score(self.session_id))
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
