from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    send_file,
    abort
)
import os

from database.db_service import DatabaseService

try:
    from services.kmeans_service import KMeansService
except Exception:
    KMeansService = None


dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard"
)


@dashboard_bp.route("/")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]

    # =========================================================
    # CANDIDATE
    # =========================================================

    candidate = DatabaseService.get_candidate_profile(user_id)

    # =========================================================
    # GET ALL EXAMS
    # =========================================================

    DatabaseService.init_db()

    conn = DatabaseService.get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                title,
                description,
                duration AS duration_minutes,
                total_marks
            FROM exams
            WHERE title NOT GLOB '__*'
            ORDER BY id
        """)

        exams = [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()

    # =========================================================
    # GET ALL EXAM SESSIONS FOR THIS CANDIDATE
    # =========================================================

    conn = DatabaseService.get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                es.id AS session_id,
                es.exam_id,
                es.start_time,
                es.end_time,
                es.status,
                es.integrity_score,
                es.score,
                es.percentage,
                es.termination_reason,

                e.title AS exam_title,
                e.description,
                e.duration AS duration_minutes,
                e.total_marks

            FROM exam_sessions es

            INNER JOIN exams e
                ON es.exam_id = e.id

            WHERE es.candidate_id = ?

            ORDER BY es.id DESC
        """, (user_id,))

        session_rows = [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()

    # =========================================================
    # FIND LATEST ATTEMPT FOR EACH EXAM
    # =========================================================

    latest_attempts = {}

    for row in session_rows:

        exam_id = row["exam_id"]

        if exam_id not in latest_attempts:
            latest_attempts[exam_id] = row

    # =========================================================
    # ASSIGNMENTS
    # =========================================================

    assignments = []

    completed_count = 0
    pending_count = 0

    for exam in exams:

        exam_id = exam["id"]

        attempt = latest_attempts.get(exam_id)

        # -----------------------------------------------------
        # NO ATTEMPT
        # -----------------------------------------------------

        if attempt is None:

            assignment = {
                "exam_id": exam_id,
                "exam_title": exam["title"],
                "title": exam["title"],
                "description": exam["description"],
                "duration_minutes": exam["duration_minutes"],
                "total_marks": exam["total_marks"],

                "session_id": None,
                "status": "AVAILABLE",

                "score": None,
                "percentage": None,
                "integrity_score": 100,

                "start_time": None,
                "end_time": None,
                "termination_reason": None
            }

            assignments.append(assignment)

            pending_count += 1

            continue

        # -----------------------------------------------------
        # EXISTING ATTEMPT
        # -----------------------------------------------------

        status = str(
            attempt.get("status") or ""
        ).upper()

        # -----------------------------------------------------
        # COMPLETED
        # -----------------------------------------------------

        if status == "COMPLETED":

            completed_count += 1
            assignments.append({
                "exam_id": exam_id,
                "exam_title": exam["title"],
                "title": exam["title"],
                "description": exam["description"],
                "duration_minutes": exam["duration_minutes"],
                "total_marks": exam["total_marks"],
                "session_id": attempt["session_id"],
                "status": "COMPLETED",
                "score": attempt.get("score"),
                "percentage": attempt.get("percentage"),
                "integrity_score": attempt.get("integrity_score"),
                "start_time": attempt.get("start_time"),
                "end_time": attempt.get("end_time"),
                "termination_reason": None
            })

        # -----------------------------------------------------
        # TERMINATED
        # -----------------------------------------------------

        elif status == "TERMINATED":

            pending_count += 1
            assignments.append({
                "exam_id": exam_id,
                "exam_title": exam["title"],
                "title": exam["title"],
                "description": exam["description"],
                "duration_minutes": exam["duration_minutes"],
                "total_marks": exam["total_marks"],
                "session_id": None,
                "status": "AVAILABLE",
                "score": None,
                "percentage": None,
                "integrity_score": 100,
                "start_time": None,
                "end_time": None,
                "termination_reason": attempt.get("termination_reason")
            })

        # -----------------------------------------------------
        # IN PROGRESS
        # -----------------------------------------------------

        elif status == "IN_PROGRESS":

            pending_count += 1

            assignment = {
                "exam_id": exam_id,
                "exam_title": exam["title"],
                "title": exam["title"],
                "description": exam["description"],
                "duration_minutes": exam["duration_minutes"],
                "total_marks": exam["total_marks"],

                "session_id": attempt["session_id"],
                "status": "IN_PROGRESS",

                "score": attempt["score"],
                "percentage": attempt["percentage"],
                "integrity_score": attempt["integrity_score"],

                "start_time": attempt["start_time"],
                "end_time": attempt["end_time"],
                "termination_reason": attempt[
                    "termination_reason"
                ]
            }

            assignments.append(assignment)

        elif status == "ACTIVE":
            pending_count += 1
            assignments.append({
                "exam_id": exam_id,
                "exam_title": exam["title"],
                "title": exam["title"],
                "description": exam["description"],
                "duration_minutes": exam["duration_minutes"],
                "total_marks": exam["total_marks"],
                "session_id": attempt["session_id"],
                "status": "IN_PROGRESS",
                "score": attempt.get("score"),
                "percentage": attempt.get("percentage"),
                "integrity_score": attempt.get("integrity_score"),
                "start_time": attempt.get("start_time"),
                "end_time": attempt.get("end_time"),
                "termination_reason": attempt.get("termination_reason")
            })

    # =========================================================
    # HISTORY
    #
    # ONLY COMPLETED / TERMINATED ATTEMPTS
    # =========================================================

    history = []

    for attempt in session_rows:

        status = str(
            attempt.get("status") or ""
        ).upper()

        if status in (
            "COMPLETED",
            "TERMINATED"
        ):

            history.append(attempt)

    # =========================================================
    # ANALYTICS
    # =========================================================

    analytics = {
        "total_exams": len(exams),
        "pending": pending_count,
        "completed": completed_count
    }

    # Keep the template contract stable regardless of the source attempt state.
    for assignment in assignments:
        assignment["id"] = assignment.get("id", assignment.get("exam_id"))
        assignment["title"] = assignment.get("title", assignment.get("exam_title", "Untitled Exam"))
        assignment["description"] = assignment.get("description") or ""
        assignment["duration"] = assignment.get("duration", assignment.get("duration_minutes", 0))
        assignment["duration_minutes"] = assignment.get("duration_minutes", assignment["duration"])
        assignment["total_marks"] = assignment.get("total_marks", 0)
        assignment["status"] = assignment.get("status", "AVAILABLE")
        assignment["score"] = assignment.get("score")
        assignment["percentage"] = assignment.get("percentage")
        assignment["integrity_score"] = assignment.get("integrity_score", 100)
        assignment["completed"] = assignment["status"] == "COMPLETED"
        assignment["available_for_attempt"] = not assignment["completed"]

    # =========================================================
    # K-MEANS
    # =========================================================

    kmeans_analysis = None

    if KMeansService:

        try:
            kmeans_analysis = KMeansService.analyze()
        except Exception as e:
            print(
                "K-Means dashboard error:",
                e
            )

    # =========================================================
    # RENDER
    # =========================================================

    return render_template(
        "dashboard.html",

        candidate=candidate,

        assignments=assignments,

        analytics=analytics,

        kmeans_analysis=kmeans_analysis
    )


@dashboard_bp.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    submissions = DatabaseService.get_user_submissions(session["user_id"]) or []
    total_attempts = len(submissions)
    completed_attempts = sum(
        1 for item in submissions if item.get("status") == "COMPLETED"
    )
    terminated_attempts = sum(
        1 for item in submissions if item.get("status") == "TERMINATED"
    )
    average_percentage = 0
    average_integrity = 0

    if total_attempts:
        average_percentage = round(
            sum(float(item.get("percentage") or 0) for item in submissions) / total_attempts,
            1
        )
        average_integrity = round(
            sum(float(item.get("integrity_score") or 0) for item in submissions) / total_attempts,
            1
        )

    for item in submissions:
        item.setdefault("exam_title", "Untitled Exam")
        item.setdefault("attempt_number", 0)
        item.setdefault("completed_at", None)
        item.setdefault("start_time", None)
        item.setdefault("end_time", None)
        item.setdefault("duration", 0)
        item.setdefault("score", 0)
        item.setdefault("total", 0)
        item.setdefault("percentage", 0)
        item.setdefault("integrity_score", 0)
        item.setdefault("violations", 0)
        item.setdefault("termination_reason", None)
        item["status"] = str(item.get("status") or "UNKNOWN").upper()

    history_summary = {
        "total_attempts": total_attempts,
        "completed": completed_attempts,
        "terminated": terminated_attempts,
        "average_score": average_percentage,
        "average_integrity": average_integrity,
    }

    return render_template(
        "history.html",
        candidate=DatabaseService.get_candidate_profile(session["user_id"]),
        history=submissions,
        history_summary=history_summary,
    )


@dashboard_bp.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    submissions = DatabaseService.get_user_submissions(session["user_id"])
    exams = DatabaseService.get_all_exams()
    completed_exam_ids = {
        row["exam_id"] for row in submissions if row.get("status") == "COMPLETED"
    }
    return render_template(
        "profile.html",
        candidate=DatabaseService.get_candidate_profile(session["user_id"]),
        profile_stats={
            "total_assignments": len(exams),
            "completed": len(completed_exam_ids),
            "pending": max(0, len(exams) - len(completed_exam_ids)),
            "attempts": len(submissions)
        }
    )


@dashboard_bp.route("/profile/photo")
def profile_photo():
    if "user_id" not in session:
        abort(404)
    candidate = DatabaseService.get_candidate_profile(session["user_id"])
    photo_path = candidate.get("photo_path") if candidate else None
    if not photo_path:
        abort(404)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidate_path = str(photo_path)
    resolved_path = os.path.abspath(candidate_path) if os.path.isabs(candidate_path) else os.path.abspath(os.path.join(project_root, candidate_path))
    upload_root = os.path.abspath(os.path.join(project_root, "uploads"))
    if not resolved_path.startswith(upload_root + os.sep) or not os.path.isfile(resolved_path):
        abort(404)
    return send_file(resolved_path)


# =============================================================
# REPORT / RESULT
# =============================================================

@dashboard_bp.route(
    "/report/<int:session_id>"
)
def view_report(session_id):

    if "user_id" not in session:
        return redirect(
            url_for("auth.login")
        )

    user_id = session["user_id"]

    candidate = DatabaseService.get_candidate_profile(
        user_id
    )

    # ---------------------------------------------------------
    # Get requested session belonging to logged-in candidate
    # ---------------------------------------------------------

    conn = DatabaseService.get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                es.id AS session_id,
                es.exam_id,
                es.start_time,
                es.end_time,
                es.status,
                es.integrity_score,
                es.score,
                es.percentage,
                es.termination_reason,

                e.title AS exam_title,
                e.description,
                e.duration AS duration_minutes,
                e.total_marks

            FROM exam_sessions es

            INNER JOIN exams e
                ON es.exam_id = e.id

            WHERE es.id = ?
              AND es.candidate_id = ?

            LIMIT 1
        """, (
            session_id,
            user_id
        ))

        row = cursor.fetchone()

    finally:
        conn.close()

    if row is None:
        return "Exam report not found.", 404

    report = dict(row)

    # ---------------------------------------------------------
    # Completed result
    # ---------------------------------------------------------

    if report["status"] == "COMPLETED":

        return render_template(
            "report.html",
            candidate=candidate,
            report=report
        )

    # ---------------------------------------------------------
    # Terminated exam
    # ---------------------------------------------------------

    if report["status"] == "TERMINATED":

        return render_template(
            "exam_terminated.html",

            candidate=candidate,

            reason=report.get(
                "termination_reason"
            ) or "Examination terminated.",

            termination_reason=report.get(
                "termination_reason"
            ) or "Examination terminated.",

            exam=report,

            session_id=session_id
        )

    return "This examination has not been completed.", 400