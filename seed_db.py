"""Idempotent demo seeding against the canonical DatabaseService schema."""

from database.db_service import DatabaseService

EXAMS = [
    ("Python Core & Advanced Concepts", "Python fundamentals, OOP, and data structures.", 60, 100),
    ("Web Development with Flask & SQL", "Flask routing, database integration, and APIs.", 45, 100),
    ("AI & Machine Learning Essentials", "Machine learning basics, computer vision, and proctoring logic.", 30, 100),
]

QUESTION_SETS = {
    "Python Core & Advanced Concepts": [
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
    ],
    "Web Development with Flask & SQL": [
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
    ],
    "AI & Machine Learning Essentials": [
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
    ],
}


def seed_database():
    DatabaseService.init_db()
    conn = DatabaseService.get_connection()
    try:
        for title, description, duration, total_marks in EXAMS:
            conn.execute("""
                INSERT INTO exams (title, description, duration, total_marks, is_active)
                SELECT ?, ?, ?, ?, 1
                WHERE NOT EXISTS (SELECT 1 FROM exams WHERE title = ?)
            """, (title, description, duration, total_marks, title))
        conn.commit()
        exams = {row["title"]: row["id"] for row in conn.execute("SELECT id, title FROM exams")}
    finally:
        conn.close()

    for title, questions in QUESTION_SETS.items():
        exam_id = exams.get(title)
        if not exam_id:
            continue
        existing_count = len(DatabaseService.get_questions_for_exam(exam_id))
        if existing_count >= 10:
            continue
        for question_text, options, correct_index in questions:
            DatabaseService.add_question(
                exam_id,
                question_text,
                "mcq",
                1,
                [{"text": value, "is_correct": int(index == correct_index)} for index, value in enumerate(options)]
            )
    print("Canonical database seeding complete.")


if __name__ == "__main__":
    seed_database()
