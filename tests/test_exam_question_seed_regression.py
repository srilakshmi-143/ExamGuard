import unittest
import uuid

from database.db_service import DatabaseService


class ExamQuestionSeedRegressionTests(unittest.TestCase):
    def setUp(self):
        DatabaseService.init_db()
        self.username = f"regression_exam_user_{uuid.uuid4().hex[:8]}"
        self.email = f"regression_exam_{uuid.uuid4().hex[:12]}@example.com"
        self.user_id = DatabaseService.create_user(
            self.username,
            "hashed-password",
            "student",
            self.email,
        )
        self.assertIsNotNone(self.user_id)

        self.exam_id = DatabaseService.create_exam(
            f"Candidate Visible Exam {uuid.uuid4().hex[:8]}",
            "Exam should never be empty.",
            20,
            100,
            40.0,
            self.user_id,
        )
        self.assertIsNotNone(self.exam_id)

        conn = DatabaseService.get_connection()
        conn.execute("DELETE FROM questions WHERE exam_id = ?", (self.exam_id,))
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = DatabaseService.get_connection()
        conn.execute("DELETE FROM questions WHERE exam_id = ?", (self.exam_id,))
        conn.execute("DELETE FROM exams WHERE id = ?", (self.exam_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (self.user_id,))
        conn.commit()
        conn.close()

    def test_get_questions_for_exam_repairs_empty_exam(self):
        questions = DatabaseService.get_questions_for_exam(self.exam_id)
        self.assertGreater(len(questions), 0)
        self.assertGreaterEqual(len(questions), 5)
        self.assertTrue(all(q.get("question") for q in questions))


if __name__ == "__main__":
    unittest.main()
