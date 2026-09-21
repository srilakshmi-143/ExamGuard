import os
import base64
import uuid
import sqlite3
from pathlib import Path
from functools import wraps
from datetime import datetime

import cv2
import numpy as np

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash
)

from database.db_service import DatabaseService
from config import Config
from services.face_verifier import FaceVerifier
from services import presence_tracker


# ============================================================
# BLUEPRINT
# ============================================================

exam_bp = Blueprint("exam", __name__)

DB_PATH = Path(Config.DATABASE_PATH)

face_verifier = FaceVerifier()


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("auth.login"))

        return func(*args, **kwargs)

    return decorated_function


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# IMAGE DECODER
# ============================================================

def decode_image_data(image_data):
    """
    Converts a browser data URL / base64 image into
    an OpenCV BGR image.
    """

    if not image_data:
        return None

    try:

        if "," in image_data:
            _, encoded = image_data.split(",", 1)
        else:
            encoded = image_data

        image_bytes = base64.b64decode(encoded)

        np_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            np_array,
            cv2.IMREAD_COLOR
        )

        return frame

    except Exception as e:

        print(
            "[Face Verification] Image decode error:",
            e
        )

        return None


# ============================================================
# REGISTERED PHOTO PATH
# ============================================================

def get_profile_photo_path(user):
    """
    Resolves the registered candidate photograph path.
    """

    if not user:
        return None

    photo_path = user.get("photo_path")

    if not photo_path:
        return None

    photo_path = str(photo_path)

    # --------------------------------------------------------
    # Absolute path
    # --------------------------------------------------------

    if os.path.isabs(photo_path):

        if os.path.exists(photo_path):
            return photo_path

    # --------------------------------------------------------
    # Path relative to project root
    # --------------------------------------------------------

    project_root = Path(
        __file__
    ).resolve().parent.parent

    possible_paths = [

        project_root / photo_path,

        project_root / "uploads" / photo_path,

        project_root / "uploads" / "registration_photos" / photo_path,

        Path(photo_path)

    ]

    for path in possible_paths:

        try:

            if path.exists():
                return str(path.resolve())

        except Exception:
            continue

    return None


# ============================================================
# CHECK PREVIOUS EXAM ATTEMPT
# ============================================================

def get_previous_attempt(user_id, exam_id):
    """
    Returns the candidate's previous attempt for this exam.

    Both COMPLETED and TERMINATED attempts count as an
    already-used attempt.
    """

    conn = get_db_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM exam_submissions
            WHERE user_id = ?
              AND exam_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                user_id,
                exam_id
            )
        )

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None

    finally:

        conn.close()


# ============================================================
# GET VERIFIED EXAM SESSION
# ============================================================

def get_verified_exam_session(user_id, exam_id):
    """
    Returns an active exam session only if:
    1. It belongs to the logged-in candidate.
    2. It belongs to the requested exam.
    3. Face verification was successful.
    4. Session is still active.
    """

    conn = get_db_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM exam_sessions
            WHERE candidate_id = ?
              AND exam_id = ?
              AND face_verified = 1
              AND status = 'ACTIVE'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                user_id,
                exam_id
            )
        )

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None

    finally:

        conn.close()


# ============================================================
# DASHBOARD
# ============================================================

@exam_bp.route("/dashboard")
@login_required
def dashboard():

    user_id = session.get("user_id")

    user = DatabaseService.get_user_by_email(
        session.get("candidate_email")
    )

    if not user:
        return redirect(
            url_for("auth.logout")
        )

    # --------------------------------------------------------
    # Get all exams
    # --------------------------------------------------------

    conn = get_db_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                title,
                description,
                duration,
                total_marks
            FROM exams
            ORDER BY id
            """
        )

        exams = [
            dict(row)
            for row in cursor.fetchall()
        ]

        # ----------------------------------------------------
        # Get latest attempt for every exam
        # ----------------------------------------------------

        attempts = {}

        cursor.execute(
            """
            SELECT *
            FROM exam_submissions
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        )

        for row in cursor.fetchall():

            row_dict = dict(row)

            exam_id = row_dict.get("exam_id")

            if exam_id not in attempts:
                attempts[exam_id] = row_dict

    finally:

        conn.close()

    # --------------------------------------------------------
    # Build dashboard statistics
    # --------------------------------------------------------

    total = len(exams)

    completed = 0
    terminated = 0
    pending = 0

    for exam in exams:

        exam_id = exam["id"]

        attempt = attempts.get(exam_id)

        if not attempt:

            pending += 1
            continue

        status = str(
            attempt.get("status", "")
        ).strip().lower()

        if status in (
            "completed",
            "submitted"
        ):

            completed += 1

        elif status in (
            "terminated",
            "terminated_violation"
        ):

            terminated += 1

        else:

            # Any existing attempt should not become
            # accidentally retakeable.
            pending += 0

    stats = {
        "total": total,
        "completed": completed,
        "terminated": terminated,
        "pending": pending
    }

    # --------------------------------------------------------
    # K-MEANS ANALYSIS
    # --------------------------------------------------------

    kmeans_analysis = None

    try:

        from services.kmeans_service import KMeansService

        kmeans_analysis = KMeansService.analyze()

    except Exception as e:

        print(
            "[Dashboard] K-Means analysis unavailable:",
            e
        )

    # --------------------------------------------------------
    # Render dashboard
    # --------------------------------------------------------

    return render_template(
        "dashboard.html",
        candidate=user,
        assignments=exams,
        attempts=attempts,
        results=attempts,
        stats=stats,
        kmeans_analysis=kmeans_analysis
    )


# ============================================================
# START / VERIFY EXAM
# ============================================================

@exam_bp.route(
    "/exam/verify/<int:assignment_id>",
    methods=["GET"]
)
@login_required
def pre_exam_verification(assignment_id):

    user_id = session.get("user_id")

    if not user_id:

        return redirect(
            url_for("auth.login")
        )

    # --------------------------------------------------------
    # Get exam
    # --------------------------------------------------------

    assignment = DatabaseService.get_assignment_by_id(
        assignment_id
    )

    if not assignment:
        flash(
            "Exam assignment not found.",
            "danger"
        )
        return redirect(url_for('dashboard.dashboard'))

    # ========================================================
    # PREVENT RETAKING COMPLETED / TERMINATED EXAMS
    # ========================================================

    conn = DatabaseService.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                es.id AS session_id,
                es.exam_id,
                es.status,
                es.start_time,
                es.end_time,
                es.integrity_score,
                es.score,
                es.percentage,
                es.termination_reason
            FROM exam_sessions es
            WHERE es.candidate_id = ?
              AND es.exam_id = ?
            ORDER BY es.id DESC
        """, (
            user_id,
            assignment_id
        ))

        previous_attempts = [
            dict(row)
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()

    previous_attempt = None
    if previous_attempts:
        previous_attempt = previous_attempts[0]

    if previous_attempt:

        previous_status = str(
            previous_attempt.get("status", "")
        ).upper()

        if previous_status == "COMPLETED":

            return redirect(
                url_for(
                    "dashboard.view_report",
                    session_id=previous_attempt["session_id"]
                )
            )

    # Clear any previous verification state
    session.pop("current_session_id", None)
    session.pop("exam_session_token", None)

    # --------------------------------------------------------
    # Create a NEW verification session
    # --------------------------------------------------------

    session_token = (
        "EXAM-"
        + uuid.uuid4().hex[:12].upper()
    )

    session_id = DatabaseService.create_exam_session(
        session_token,
        user_id,
        assignment_id
    )

    if not session_id:

        return (
            "Unable to create examination session.",
            500
        )

    # --------------------------------------------------------
    # Store current exam session in Flask session
    # --------------------------------------------------------

    session["current_session_id"] = session_id
    session["current_exam_session_id"] = session_id
    session["assignment_id"] = assignment_id

    session["exam_session_token"] = session_token

    # --------------------------------------------------------
    # Render verification page
    # --------------------------------------------------------

    return render_template(
        "verify.html",
        session_id=session_id,
        session_token=session_token,
        exam=assignment,
        assignment=assignment
    )


# Backward compatibility alias function
def verify_exam(assignment_id):
    return pre_exam_verification(assignment_id)


# ============================================================
# ALIAS: START EXAM
#
# Dashboard can use either /exam/verify/<id>
# or /exam/start/<id>.
# ============================================================

@exam_bp.route(
    "/exam/start/<int:exam_id>",
    methods=["GET"]
)
@login_required
def start_exam(exam_id):

    user_id = session.get("user_id")

    if not user_id:

        return redirect(
            url_for("auth.login")
        )

    assignment = DatabaseService.get_exam_by_id(
        exam_id
    )

    # ========================================================
    # NEVER ALLOW RETAKE OF COMPLETED / TERMINATED EXAM
    # ========================================================

    conn = DatabaseService.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                es.id AS session_id,
                es.exam_id,
                es.status,
                es.start_time,
                es.end_time,
                es.integrity_score,
                es.score,
                es.percentage,
                es.termination_reason
            FROM exam_sessions es
            WHERE es.candidate_id = ?
              AND es.exam_id = ?
            ORDER BY es.id DESC
        """, (
            user_id,
            exam_id
        ))

        previous_attempts = [
            dict(row)
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()

    previous_attempt = None
    if previous_attempts:
        previous_attempt = previous_attempts[0]

    if previous_attempt:

        previous_status = str(
            previous_attempt.get("status", "")
        ).upper()

        if previous_status == "COMPLETED":

            return redirect(
                url_for(
                    "dashboard.view_report",
                    session_id=previous_attempt["session_id"]
                )
            )

    if not assignment:

        return (
            "Examination not found.",
            404
        )

    # --------------------------------------------------------
    # Send candidate to identity verification
    # --------------------------------------------------------

    return redirect(
        url_for(
            "exam.pre_exam_verification",
            assignment_id=exam_id
        )
    )


# ============================================================
# FACE VERIFICATION API
# ============================================================

@exam_bp.route(
    "/api/verify_face",
    methods=["POST"]
)
@login_required
def verify_face():

    user_id = session.get("user_id")

    if not user_id:

        return jsonify({
            "success": False,
            "message": "User session is not active."
        }), 401

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "success": False,
                "message": "No verification data received."
            }), 400

        # ----------------------------------------------------
        # Frame can be called "frame" or "image"
        # ----------------------------------------------------

        frame_data = (
            data.get("frame")
            or data.get("image")
            or data.get("image_data")
        )

        if not frame_data:

            return jsonify({
                "success": False,
                "message": "Webcam frame was not received."
            }), 400

        live_frame = decode_image_data(
            frame_data
        )

        if live_frame is None:

            return jsonify({
                "success": False,
                "message": "Unable to decode the webcam image."
            }), 400

        # ----------------------------------------------------
        # Determine exam session
        # ----------------------------------------------------

        exam_session_id = data.get(
            "session_id"
        )

        if exam_session_id:

            try:

                exam_session_id = int(
                    exam_session_id
                )

            except (
                TypeError,
                ValueError
            ):

                return jsonify({
                    "success": False,
                    "message": "Invalid examination session."
                }), 400

        else:

            exam_session_id = session.get(
                "current_session_id"
            )

        if not exam_session_id:

            return jsonify({
                "success": False,
                "message": "No active examination session found."
            }), 400

        # ----------------------------------------------------
        # Verify session belongs to current candidate
        # ----------------------------------------------------

        exam_session = DatabaseService.get_exam_session(
            exam_session_id
        )

        if not exam_session:

            return jsonify({
                "success": False,
                "message": "Examination session was not found."
            }), 404

        if int(
            exam_session.get("candidate_id", -1)
        ) != int(user_id):

            return jsonify({
                "success": False,
                "message": "Unauthorized examination session."
            }), 403

        # ----------------------------------------------------
        # Get candidate profile
        # ----------------------------------------------------

        candidate = DatabaseService.get_user_by_email(
            session.get("candidate_email")
        )

        if not candidate:

            return jsonify({
                "success": False,
                "message": "Candidate profile was not found."
            }), 404

        # ----------------------------------------------------
        # Get registered photograph
        # ----------------------------------------------------

        registered_photo = get_profile_photo_path(
            candidate
        )

        if not registered_photo:

            return jsonify({
                "success": False,
                "message": (
                    "Registered identity photograph "
                    "could not be found."
                )
            }), 400

        print(
            "[Face Verification] Registered photo:",
            registered_photo
        )

        # ----------------------------------------------------
        # Verify face
        # ----------------------------------------------------

        verified, confidence, verification_message = (
            face_verifier.verify(
                registered_photo,
                live_frame
            )
        )

        # ----------------------------------------------------
        # Successful verification
        # ----------------------------------------------------

        if verified:

            marked = DatabaseService.mark_face_verified(
                exam_session_id
            )

            if not marked:

                return jsonify({
                    "success": False,
                    "message": (
                        "Face verified, but the "
                        "exam session could not be updated."
                    ),
                    "confidence": confidence
                }), 500

            # Store session information again
            session["current_session_id"] = (
                exam_session_id
            )
            session["current_exam_session_id"] = exam_session_id

            session["assignment_id"] = (
                exam_session.get("exam_id")
            )

            return jsonify({
                "success": True,
                "verified": True,
                "confidence": confidence,
                "message": verification_message,
                "session_id": exam_session_id,
                "exam_id": exam_session.get("exam_id"),
                "redirect": url_for(
                    "exam.start_verified_exam",
                    exam_id=exam_session.get("exam_id")
                ),
                "redirect_url": url_for(
                    "exam.start_verified_exam",
                    exam_id=exam_session.get("exam_id")
                )
            })

        # ----------------------------------------------------
        # Failed verification
        # ----------------------------------------------------

        return jsonify({
            "success": False,
            "verified": False,
            "confidence": confidence,
            "message": verification_message
        }), 400

    except Exception as e:

        print(
            "[Face Verification] ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message": (
                "Face verification failed: "
                + str(e)
            )
        }), 500


# ============================================================
# START VERIFIED EXAM
# ============================================================

@exam_bp.route(
    "/exam/start-verified/<int:exam_id>",
    methods=["GET"]
)
@login_required
def start_verified_exam(exam_id):

    user_id = session.get("user_id")

    if not user_id:

        return redirect(
            url_for("auth.login")
        )

    # --------------------------------------------------------
    # CRITICAL RETAKE CHECK
    # --------------------------------------------------------

    previous_attempt = get_previous_attempt(
        user_id,
        exam_id
    )

    if previous_attempt:

        status = str(
            previous_attempt.get("status", "")
        ).strip().lower()

        if status in (
            "completed",
            "submitted"
        ):

            return render_template(
                "exam_completed.html",
                score=previous_attempt.get(
                    "score",
                    0
                ),
                total=previous_attempt.get(
                    "total",
                    0
                ),
                percentage=previous_attempt.get(
                    "percentage",
                    0
                ),
                integrity_score=previous_attempt.get(
                    "integrity_score",
                    100
                ),
                already_attempted=True
            )

    # --------------------------------------------------------
    # Get verified active session
    # --------------------------------------------------------

    exam_session = get_verified_exam_session(
        user_id,
        exam_id
    )

    if not exam_session:

        return (
            "Identity verification is required "
            "before starting the examination.",
            403
        )

    # --------------------------------------------------------
    # Get exam
    # --------------------------------------------------------

    exam = DatabaseService.get_exam_by_id(
        exam_id
    )

    if not exam:

        return (
            "Examination not found.",
            404
        )

    # --------------------------------------------------------
    # Get questions
    # --------------------------------------------------------

    questions = DatabaseService.get_exam_questions(
        exam_id
    )

    # --------------------------------------------------------
    # Store active session
    # --------------------------------------------------------

    session["current_session_id"] = (
        exam_session["id"]
    )
    session["current_exam_session_id"] = exam_session["id"]

    session["assignment_id"] = exam_id

    # --------------------------------------------------------
    # Render exam
    # --------------------------------------------------------

    return render_template(
        "exam.html",
        session_id=exam_session["id"],
        exam=exam,
        assignment=exam,
        questions=questions,
        saved_answers=DatabaseService.get_exam_answers(exam_session["id"]),
        remaining_seconds=_remaining_exam_seconds(exam, exam_session),
        exam_started=bool(exam_session.get("active_started_at"))
    )


def _remaining_exam_seconds(exam, exam_session):
    duration_seconds = max(0, int(exam.get("duration", 0) or 0) * 60)
    active_seconds = int(exam_session.get("active_seconds") or 0)
    return max(0, duration_seconds - active_seconds)


@exam_bp.route("/exam/activate/<int:session_id>", methods=["POST"])
@login_required
def activate_exam(session_id):
    exam_session = DatabaseService.get_exam_session(session_id)
    if not exam_session or int(exam_session.get("candidate_id", -1)) != int(session["user_id"]):
        return jsonify({"status": "error", "message": "Invalid examination session."}), 403
    if exam_session.get("status") != "ACTIVE" or not exam_session.get("face_verified"):
        return jsonify({"status": "error", "message": "Identity verification is required."}), 403
    activated = DatabaseService.activate_exam_session(session_id)
    if not activated:
        return jsonify({"status": "error", "message": "The examination could not be started."}), 409
    exam = DatabaseService.get_exam_by_id(int(activated["exam_id"]))
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "remaining_seconds": _remaining_exam_seconds(exam or {}, activated)
    })


@exam_bp.route("/exam/timing/<int:session_id>", methods=["POST"])
@login_required
def exam_timing(session_id):
    data = request.get_json(silent=True) or {}
    exam_session = DatabaseService.get_exam_session(session_id)
    if not exam_session or int(exam_session.get("candidate_id", -1)) != int(session["user_id"]):
        return jsonify({"status": "error", "message": "Invalid examination session."}), 403
    if exam_session.get("status") != "ACTIVE" or not exam_session.get("active_started_at"):
        return jsonify({"status": "error", "message": "The examination is not active."}), 409
    updated = DatabaseService.update_active_time(session_id, resume=bool(data.get("resume")))
    exam = DatabaseService.get_exam_by_id(int(updated["exam_id"])) if updated else None
    remaining = _remaining_exam_seconds(exam or {}, updated or {})
    return jsonify({
        "status": "success",
        "remaining_seconds": remaining,
        "active_seconds": int((updated or {}).get("active_seconds") or 0),
        "server_status": (updated or {}).get("status"),
        "expired": remaining <= 0
    })


# ============================================================
# COMPATIBILITY ROUTE
#
# Some existing verification.html versions use:
# /exam/interface/<session_id>
# ============================================================

@exam_bp.route(
    "/exam/interface/<int:session_id>",
    methods=["GET"]
)
@login_required
def exam_interface(session_id):

    user_id = session.get("user_id")

    exam_session = DatabaseService.get_exam_session(
        session_id
    )

    if not exam_session:

        return (
            "Examination session not found.",
            404
        )

    if int(
        exam_session.get("candidate_id", -1)
    ) != int(user_id):

        return (
            "Unauthorized examination session.",
            403
        )

    if int(
        exam_session.get("face_verified", 0)
    ) != 1:

        return (
            "Identity verification is required "
            "before starting the examination.",
            403
        )

    if str(
        exam_session.get("status", "")
    ).upper() != "ACTIVE":

        return (
            "This examination session is no longer active.",
            403
        )

    exam_id = exam_session.get(
        "exam_id"
    )

    # --------------------------------------------------------
    # Retake protection
    # --------------------------------------------------------

    previous_attempt = get_previous_attempt(
        user_id,
        exam_id
    )

    if previous_attempt:

        status = str(
            previous_attempt.get("status", "")
        ).strip().lower()

        if status in (
            "completed",
            "submitted"
        ):

            return render_template(
                "exam_completed.html",
                score=previous_attempt.get(
                    "score",
                    0
                ),
                total=previous_attempt.get(
                    "total",
                    0
                ),
                percentage=previous_attempt.get(
                    "percentage",
                    0
                ),
                integrity_score=previous_attempt.get(
                    "integrity_score",
                    100
                ),
                already_attempted=True
            )

    exam = DatabaseService.get_exam_by_id(exam_id)
    questions = DatabaseService.get_exam_questions(exam_id)

    return render_template(
        "exam.html",
        session_id=session_id,
        exam=exam,
        assignment=exam,
        questions=questions,
        saved_answers=DatabaseService.get_exam_answers(session_id),
        remaining_seconds=_remaining_exam_seconds(exam, exam_session),
        exam_started=bool(exam_session.get("active_started_at"))
    )


def _current_candidate_session(user_id, exam_id):
    session_id = session.get("current_session_id")
    if not session_id:
        return None

    exam_session = DatabaseService.get_exam_session(int(session_id))
    if not exam_session:
        return None
    if int(exam_session.get("candidate_id", -1)) != int(user_id):
        return None
    if int(exam_session.get("exam_id", -1)) != int(exam_id):
        return None
    return exam_session


def _elapsed_seconds(start_time):
    if not start_time:
        return 0
    try:
        started = datetime.strptime(str(start_time).split(".")[0], "%Y-%m-%d %H:%M:%S")
        return max(0, int((datetime.utcnow() - started).total_seconds()))
    except (TypeError, ValueError):
        return 0


@exam_bp.route("/exam/submit", methods=["POST"])
@login_required
def submit_exam():
    data = request.get_json(silent=True) or {}
    user_id = session.get("user_id")
    exam_id = data.get("exam_id")

    try:
        exam_id = int(exam_id)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid exam."}), 400

    exam_session = _current_candidate_session(user_id, exam_id)
    if not exam_session or exam_session.get("status") != "ACTIVE" or not exam_session.get("face_verified"):
        return jsonify({"status": "error", "message": "An active verified exam session is required."}), 403

    exam_session = DatabaseService.update_active_time(exam_session["id"]) or exam_session

    previous_attempt = get_previous_attempt(user_id, exam_id)
    if previous_attempt and str(previous_attempt.get("status", "")).upper() == "COMPLETED":
        return jsonify({"status": "error", "message": "This examination has already been completed."}), 409

    exam = DatabaseService.get_exam_by_id(exam_id)
    if not exam:
        return jsonify({"status": "error", "message": "Exam not found."}), 404
    server_timed_out = _remaining_exam_seconds(exam, exam_session) <= 0
    questions = DatabaseService.get_exam_questions(exam_id, include_correct=True)
    answers = data.get("answers") or {}
    score = 0
    total = 0
    correct_answers = 0
    wrong_answers = 0
    unanswered = 0

    for question in questions:
        marks = int(question.get("marks") or 1)
        total += marks
        correct = str(question.get("correct_option") or "").lower()
        if correct.startswith("option_"):
            correct = correct[-1].upper()
        elif correct:
            correct = correct.upper()
        selected = str(answers.get(str(question.get("id")), "")).upper()
        if not selected:
            unanswered += 1
        elif selected == correct:
            score += marks
            correct_answers += 1
        else:
            wrong_answers += 1

    percentage = round((score / total) * 100, 2) if total else 0.0
    integrity_score = DatabaseService.get_integrity_score(exam_session["id"])
    violations = DatabaseService.get_total_violation_count(exam_session["id"])
    presence = presence_tracker.finalize(exam_session["id"])
    DatabaseService.save_presence_ratio(exam_session["id"], presence.get("presence_ratio"))

    try:
        DatabaseService.save_exam_answers(exam_session["id"], answers)
        DatabaseService.save_exam_submission(
            user_id=user_id,
            exam_id=exam_id,
            session_id=exam_session["id"],
            score=score,
            total=total,
            percentage=percentage,
            integrity_score=integrity_score,
            violations=violations,
            status="COMPLETED"
        )
        DatabaseService.save_exam_session_result(
            session_id=exam_session["id"],
            score=score,
            percentage=percentage,
            integrity_score=integrity_score,
            status="COMPLETED"
        )
        DatabaseService.update_session_status(exam_session["id"], "COMPLETED")
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 409

    session.pop("current_session_id", None)
    session.pop("current_exam_session_id", None)
    return jsonify({
        "status": "success",
        "score": score,
        "total": total,
        "percentage": percentage,
        "correct_answers": correct_answers,
        "wrong_answers": wrong_answers,
        "unanswered": unanswered,
        "timed_out": server_timed_out,
        "redirect_url": url_for("exam.exam_result", session_id=exam_session["id"])
    })


@exam_bp.route("/exam/result/<int:session_id>")
@login_required
def exam_result(session_id):
    user_id = session["user_id"]
    exam_session = DatabaseService.get_exam_session(session_id)
    if not exam_session or int(exam_session.get("candidate_id", -1)) != int(user_id):
        return "Exam result not found.", 404
    if exam_session.get("status") not in ("COMPLETED", "TERMINATED"):
        return "This exam has not been completed.", 400

    exam = DatabaseService.get_exam_by_id(exam_session["exam_id"])
    candidate = DatabaseService.get_candidate_profile(user_id)
    questions = DatabaseService.get_exam_questions(exam_session["exam_id"], include_correct=True)
    answers = DatabaseService.get_exam_answers(session_id)
    detailed_results = []
    correct_answers = wrong_answers = unanswered = 0

    for question in questions:
        selected = str(answers.get(question["id"], "")).upper()
        correct = str(question.get("correct_option") or "").upper()
        if correct.startswith("OPTION_"):
            correct = correct[-1]
        options = question.get("options") or {}
        selected_text = options.get(selected, "")
        correct_text = options.get(correct, "")
        is_correct = bool(selected and selected == correct)
        if is_correct:
            correct_answers += 1
        elif selected:
            wrong_answers += 1
        else:
            unanswered += 1
        detailed_results.append({
            "question_text": question.get("question", question.get("question_text", "")),
            "selected_option": selected,
            "selected_text": selected_text,
            "correct_option": correct,
            "correct_text": correct_text,
            "is_correct": is_correct
        })

    return render_template(
        "exam_result.html",
        exam_title=exam.get("title", "Examination") if exam else "Examination",
        candidate_name=(candidate.get("full_name") or candidate.get("username")) if candidate else "Candidate",
        score=exam_session.get("score", 0) or 0,
        total_questions=exam_session.get("score", 0) * 0 + sum(int(q.get("marks") or 1) for q in questions),
        percentage=exam_session.get("percentage", 0) or 0,
        integrity_score=exam_session.get("integrity_score", 100) or 100,
        presence_ratio=exam_session.get("presence_ratio"),
        start_time=exam_session.get("start_time"),
        end_time=exam_session.get("end_time"),
        duration_minutes=exam.get("duration") if exam else None,
        correct_answers=correct_answers,
        wrong_answers=wrong_answers,
        unanswered=unanswered,
        status=exam_session.get("status"),
        termination_reason=exam_session.get("termination_reason"),
        result_status=(
            "DISQUALIFIED" if exam_session.get("status") == "TERMINATED"
            else "PASSED" if exam and float(exam_session.get("percentage") or 0) >= float(exam.get("pass_percentage") or 40)
            else "FAILED"
        ),
        violations=DatabaseService.get_total_violation_count(session_id),
        tab_switches=DatabaseService.get_violation_count(session_id, "TAB_SWITCH"),
        face_violations=DatabaseService.get_violation_count(session_id, "FACE_ABSENT"),
        multiple_face_violations=DatabaseService.get_violation_count(session_id, "MULTIPLE_FACES"),
        fullscreen_violations=DatabaseService.get_violation_count(session_id, "FULLSCREEN_EXIT"),
        phone_violations=DatabaseService.get_violation_count(session_id, "PHONE_DETECTED"),
        detailed_results=detailed_results,
        session_id=session_id
    )


@exam_bp.route("/exam/log_violation", methods=["POST"])
@login_required
def log_violation():
    data = request.get_json(silent=True) or {}
    session_id = session.get("current_session_id")
    if not session_id:
        return jsonify({"status": "error", "message": "No active exam session."}), 400

    event_type = str(data.get("type", "SECURITY_EVENT")).upper().replace(" ", "_")
    score = DatabaseService.log_suspicious_event(
        int(session_id),
        event_type,
        "MEDIUM",
        data.get("details", ""),
        15 if event_type == "TAB_SWITCH" else 5
    )
    return jsonify({"status": "success", "current_integrity_score": score})


@exam_bp.route("/api/save_answer", methods=["POST"])
@login_required
def save_answer():
    data = request.get_json(silent=True) or {}
    session_id = session.get("current_session_id")
    question_id = data.get("question_id")
    selected_option = data.get("selected_option", "")
    if not session_id or not str(question_id).isdigit():
        return jsonify({"status": "error", "message": "Invalid answer request."}), 400

    exam_session = DatabaseService.get_exam_session(int(session_id))
    if (
        not exam_session
        or int(exam_session.get("candidate_id", -1)) != int(session["user_id"])
        or exam_session.get("status") != "ACTIVE"
    ):
        return jsonify({"status": "error", "message": "Inactive or unauthorized exam session."}), 403

    DatabaseService.save_exam_answers(
        int(session_id),
        {str(question_id): selected_option}
    )
    return jsonify({"status": "success"})


@exam_bp.route("/api/terminate_exam", methods=["POST"])
@login_required
def terminate_exam():
    data = request.get_json(silent=True) or {}
    user_id = session.get("user_id")
    exam_id = data.get("exam_id")
    exam_session = _current_candidate_session(user_id, exam_id)
    if not exam_session:
        return jsonify({"status": "error", "message": "Invalid exam session."}), 403

    reason = data.get("reason") or "Examination terminated."
    DatabaseService.update_session_status(exam_session["id"], "TERMINATED", reason)

    DatabaseService.save_exam_submission(
        user_id=user_id,
        exam_id=int(exam_id),
        session_id=exam_session["id"],
        score=0,
        total=0,
        percentage=0.0,
        integrity_score=DatabaseService.get_integrity_score(exam_session["id"]),
        violations=DatabaseService.get_total_violation_count(exam_session["id"]),
        status="TERMINATED",
        termination_reason=reason
    )

    session.pop("current_session_id", None)
    session.pop("current_exam_session_id", None)
    return jsonify({
        "status": "success",
        "message": reason,
        "redirect_url": url_for("exam.exam_result", session_id=exam_session["id"])
    })