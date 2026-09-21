import sqlite3
from config import Config


def add_sample_exams():

    conn = sqlite3.connect(Config.DATABASE_PATH)
    cursor = conn.cursor()

    exams = [
        {
            "title": "General Knowledge & Aptitude Test",
            "description": "Assessment covering general knowledge, aptitude and logical reasoning.",
            "duration": 30,
            "total_marks": 50,
            "pass_marks": 20,
            "questions": [
                (
                    "Which data structure follows FIFO (First In First Out)?",
                    "Stack",
                    "Queue",
                    "Tree",
                    "Graph",
                    "B"
                ),
                (
                    "What is the default port for HTTP?",
                    "21",
                    "22",
                    "80",
                    "443",
                    "C"
                ),
                (
                    "Which SQL command is used to retrieve data?",
                    "INSERT",
                    "SELECT",
                    "UPDATE",
                    "DELETE",
                    "B"
                ),
                (
                    "Which number is a prime number?",
                    "12",
                    "15",
                    "17",
                    "21",
                    "C"
                ),
                (
                    "What is 15 × 4?",
                    "45",
                    "50",
                    "60",
                    "75",
                    "C"
                )
            ]
        },
        {
            "title": "Python Programming Assessment",
            "description": "Technical assessment covering Python programming fundamentals.",
            "duration": 30,
            "total_marks": 50,
            "pass_marks": 25,
            "questions": [
                (
                    "Which keyword is used to define a function in Python?",
                    "function",
                    "def",
                    "func",
                    "define",
                    "B"
                ),
                (
                    "Which data type stores key-value pairs?",
                    "List",
                    "Tuple",
                    "Dictionary",
                    "Set",
                    "C"
                ),
                (
                    "Which symbol is used for comments in Python?",
                    "//",
                    "/*",
                    "#",
                    "<!--",
                    "C"
                ),
                (
                    "What is the output type of len('ExamGuard')?",
                    "String",
                    "Integer",
                    "Float",
                    "Boolean",
                    "B"
                ),
                (
                    "Which library is commonly used for numerical computing?",
                    "NumPy",
                    "Flask",
                    "Django",
                    "Tkinter",
                    "A"
                )
            ]
        },
        {
            "title": "Database & SQL Security Assessment",
            "description": "Assessment covering SQL, databases and basic database security concepts.",
            "duration": 30,
            "total_marks": 50,
            "pass_marks": 25,
            "questions": [
                (
                    "Which command is used to create a database table?",
                    "CREATE",
                    "SELECT",
                    "FETCH",
                    "READ",
                    "A"
                ),
                (
                    "Which SQL command modifies existing records?",
                    "INSERT",
                    "UPDATE",
                    "CREATE",
                    "SELECT",
                    "B"
                ),
                (
                    "Which key uniquely identifies a row?",
                    "Foreign Key",
                    "Primary Key",
                    "Candidate Value",
                    "Index Value",
                    "B"
                ),
                (
                    "Which SQL command removes a table?",
                    "DELETE",
                    "REMOVE",
                    "DROP",
                    "CLEAR",
                    "C"
                ),
                (
                    "What does SQL stand for?",
                    "Structured Query Language",
                    "Simple Question Language",
                    "System Query Logic",
                    "Structured Question List",
                    "A"
                )
            ]
        }
    ]

    try:

        for exam in exams:

            # Check whether this exam already exists
            cursor.execute(
                """
                SELECT id
                FROM exams
                WHERE title = ?
                """,
                (exam["title"],)
            )

            existing = cursor.fetchone()

            if existing:
                exam_id = existing[0]

                print(
                    f"Exam already exists: {exam['title']}"
                )

            else:

                cursor.execute(
                    """
                    INSERT INTO exams (
                        title,
                        description,
                        duration,
                        total_marks,
                        pass_percentage
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        exam["title"],
                        exam["description"],
                        exam["duration"],
                        exam["total_marks"],
                        exam["pass_marks"] * 100.0 / exam["total_marks"]
                    )
                )

                exam_id = cursor.lastrowid

                print(
                    f"Added exam: {exam['title']}"
                )

            # Add questions only if this exam has no questions
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM questions
                WHERE exam_id = ?
                """,
                (exam_id,)
            )

            question_count = cursor.fetchone()[0]

            if question_count == 0:

                question_rows = []

                for number, question in enumerate(
                    exam["questions"],
                    start=1
                ):

                    question_rows.append(
                        (
                            exam_id,
                            question[0],
                            question[1],
                            question[2],
                            question[3],
                            question[4],
                            question[5],
                            10
                        )
                    )

                cursor.executemany(
                    """
                    INSERT INTO questions (
                        exam_id,
                        question_text,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        correct_option,
                        marks
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    question_rows
                )

                print(
                    f"  Added {len(question_rows)} questions."
                )

            else:

                print(
                    f"  Questions already exist: {question_count}"
                )

        conn.commit()

        print()
        print("==========================================")
        print("ASSIGNMENTS ADDED SUCCESSFULLY")
        print("==========================================")

    except Exception as e:

        conn.rollback()

        print(
            "ERROR:",
            e
        )

        raise

    finally:

        conn.close()


if __name__ == "__main__":
    add_sample_exams()