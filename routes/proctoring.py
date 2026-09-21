from flask import Blueprint, request, jsonify, session, url_for
import cv2
import numpy as np
import base64
import sqlite3
import os
from datetime import datetime
from pathlib import Path

from services.face_detector import FaceDetector
from services.face_verifier import FaceVerifier
from services.object_detector import ObjectDetector
from services.decision_engine import DecisionEngine
from config import Config
from database.db_service import DatabaseService
from services import presence_tracker
from services.integrity_engine import IntegrityEngine


proctoring_bp = Blueprint('proctoring', __name__)

DB_PATH = Path(Config.DATABASE_PATH)

face_detector = FaceDetector()
face_verifier = FaceVerifier()
object_detector = ObjectDetector()
decision_engine = DecisionEngine()


def decode_base64_frame(data_url):

    if not data_url:
        return None

    try:
        if "," in data_url:
            _, encoded = data_url.split(",", 1)
        else:
            encoded = data_url

        frame_bytes = base64.b64decode(encoded)

        np_arr = np.frombuffer(
            frame_bytes,
            np.uint8
        )

        return cv2.imdecode(
            np_arr,
            cv2.IMREAD_COLOR
        )

    except Exception:
        return None


def _save_phone_evidence(session_id, frame, phone_result):
    if not phone_result.get("confirmed") or frame is None:
        return None
    evidence_dir = os.path.join(Config.PHONE_EVIDENCE_FOLDER, f"session_{int(session_id)}")
    os.makedirs(evidence_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"phone_detected_{timestamp}.jpg"
    absolute_path = os.path.join(evidence_dir, filename)
    if not cv2.imwrite(absolute_path, frame):
        return None
    project_root = os.path.dirname(os.path.dirname(__file__))
    relative_path = os.path.relpath(absolute_path, project_root).replace(os.sep, "/")
    conn = DatabaseService.get_connection()
    try:
        event_row = conn.execute("""
            SELECT id FROM proctoring_logs
            WHERE session_id = ? AND event_type = 'PHONE_DETECTED'
            ORDER BY id DESC LIMIT 1
        """, (session_id,)).fetchone()
        cursor = conn.execute("""
            INSERT INTO evidence (session_id, event_id, event_type, file_path, description)
            VALUES (?, ?, 'PHONE_DETECTED', ?, ?)
        """, (session_id, event_row["id"] if event_row else None, relative_path, f"Confirmed phone detection at confidence {phone_result.get('confidence', 0):.3f}"))
        conn.commit()
        return {"evidence_id": cursor.lastrowid, "file_path": relative_path}
    finally:
        conn.close()


@proctoring_bp.route('/api/monitor_frame', methods=['POST'])
@proctoring_bp.route('/api/process_frame', methods=['POST'])
def monitor_frame():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Login required."}), 401

    session_id = session.get('current_exam_session_id') or session.get('current_session_id')
    if not session_id:
        return jsonify({"status": "error", "message": "No active exam session."}), 400

    data = request.get_json(silent=True) or {}
    frame = decode_base64_frame(data.get('image_data') or data.get('frame'))
    if frame is None:
        return jsonify({"status": "error", "message": "Invalid frame data."}), 400

    exam_session = DatabaseService.get_exam_session(int(session_id))
    if not exam_session or int(exam_session.get('candidate_id', -1)) != int(session['user_id']):
        return jsonify({"status": "error", "message": "Invalid exam session."}), 403
    if exam_session.get("status") != "ACTIVE":
        return jsonify({
            "status": "terminated",
            "action": "TERMINATE",
            "message": exam_session.get("termination_reason") or "This examination session is no longer active."
        }), 409

    face_status, _, face_count = face_detector.detect_faces(frame)
    phone_result = object_detector.detect_phone(frame, int(session_id))
    phone_detected = bool(phone_result.get("confirmed"))
    conn = DatabaseService.get_connection()
    try:
        response = decision_engine.evaluate_frame(
            conn,
            int(session_id),
            face_count,
            face_status,
            phone_detected
        )
    finally:
        conn.close()

    evidence = _save_phone_evidence(session_id, frame, phone_result)

    if response.get('action') == 'TERMINATE':
        reason = response.get('reason') or 'Integrity rule violation.'
        DatabaseService.update_session_status(
            int(session_id),
            'TERMINATED',
            reason
        )
        DatabaseService.save_exam_submission(
            user_id=int(session['user_id']),
            exam_id=int(exam_session['exam_id']),
            session_id=int(session_id),
            score=0,
            total=0,
            percentage=0.0,
            integrity_score=DatabaseService.get_integrity_score(int(session_id)),
            violations=DatabaseService.get_total_violation_count(int(session_id)),
            status='TERMINATED',
            termination_reason=reason
        )
        presence = presence_tracker.finalize(int(session_id))
        DatabaseService.save_presence_ratio(int(session_id), presence.get("presence_ratio"))
        session.pop('current_session_id', None)
        session.pop('current_exam_session_id', None)

    return jsonify({
        "status": "success",
        "face_detected": face_count == 1,
        "face_status": face_status,
        "face_count": face_count,
        "phone_detected": phone_detected,
        "phone_detection": {**phone_result, "evidence": evidence},
        "integrity_score": DatabaseService.get_integrity_score(int(session_id)),
        "action": response.get('action'),
        "message": response.get('reason'),
        "missing_seconds": response.get('missing_seconds', 0),
        "should_terminate": response.get('action') == 'TERMINATE',
        "redirect_url": url_for('exam.exam_result', session_id=int(session_id)) if response.get('action') == 'TERMINATE' else None
    })


# =========================================================
# PRE-EXAM IDENTITY VERIFICATION
# =========================================================

@proctoring_bp.route(
    '/api/proctoring/verify',
    methods=['POST']
)
@proctoring_bp.route(
    '/api/verify_identity',
    methods=['POST']
)
def verify_identity():

    if 'user_id' not in session:
        return jsonify({
            "success": False,
            "message": "User is not logged in."
        }), 401

    data = request.get_json(silent=True) or {}

    session_id = data.get("session_id") or session.get("current_session_id")
    frame_data = data.get("frame") or data.get("image_data")

    if not session_id:
        return jsonify({
            "success": False,
            "message": "Exam session ID is missing."
        }), 400

    if not frame_data:
        return jsonify({
            "success": False,
            "message": "Live camera frame is missing."
        }), 400

    user_id = session["user_id"]

    # -----------------------------------------------------
    # Verify that this exam session belongs to this user
    # -----------------------------------------------------

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                es.id,
                es.candidate_id,
                es.exam_id,
                es.status
            FROM exam_sessions es
            WHERE es.id = ?
              AND es.candidate_id = ?
        """, (
            session_id,
            user_id
        ))

        exam_session = cursor.fetchone()

        if not exam_session:

            return jsonify({
                "success": False,
                "message": "Invalid examination session."
            }), 403

        # Do not allow verification after exam has already ended
        if exam_session["status"] in (
            "COMPLETED",
            "TERMINATED"
        ):

            return jsonify({
                "success": False,
                "message": "This examination session is no longer active."
            }), 400

        # -------------------------------------------------
        # Get registered candidate photo
        # -------------------------------------------------

        cursor.execute("""
            SELECT photo_path
            FROM users
            WHERE id = ?
        """, (
            user_id,
        ))

        profile = cursor.fetchone()

        if not profile or not profile["photo_path"]:

            return jsonify({
                "success": False,
                "message": "Registered profile photo was not found."
            }), 400

        registered_photo = profile["photo_path"]

    finally:

        conn.close()

    # -----------------------------------------------------
    # Decode live webcam image
    # -----------------------------------------------------

    live_frame = decode_base64_frame(frame_data)

    if live_frame is None:

        return jsonify({
            "success": False,
            "message": "Unable to read live camera image."
        }), 400

    # -----------------------------------------------------
    # FIRST: make sure exactly one face exists
    # -----------------------------------------------------

    try:

        face_status, _, face_count = (
            face_detector.detect_faces(live_frame)
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Face detection failed."
        }), 500

    if face_count == 0:

        return jsonify({
            "success": False,
            "message": "No face detected. Please position your face clearly in front of the camera.",
            "face_status": "NO_FACE",
            "detected_faces": 0
        })

    if face_count > 1:

        return jsonify({
            "success": False,
            "message": "Multiple faces detected. Only the registered candidate must be visible.",
            "face_status": "MULTIPLE_FACES",
            "detected_faces": face_count
        })

    # -----------------------------------------------------
    # SECOND: compare registered photo with live photo
    # -----------------------------------------------------

    try:

        success, confidence, message = face_verifier.verify(
            registered_photo,
            live_frame
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Identity verification failed."
        }), 500

    if not success:

        return jsonify({
            "success": False,
            "message": message,
            "confidence": confidence,
            "face_status": "SINGLE_FACE",
            "detected_faces": 1
        })

    # -----------------------------------------------------
    # IDENTITY MATCHED
    # -----------------------------------------------------

    conn = sqlite3.connect(DB_PATH)

    try:

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE exam_sessions
            SET face_verified = 1
            WHERE id = ?
              AND candidate_id = ?
              AND status = 'ACTIVE'
        """, (
            session_id,
            user_id
        ))

        conn.commit()

    finally:

        conn.close()

    # Store verified state in Flask session as an additional
    # server-side protection.
    session["verified_exam_session"] = int(session_id)

    return jsonify({
        "success": True,
        "message": "Identity verified successfully.",
        "confidence": confidence,
        "face_status": "SINGLE_FACE",
        "detected_faces": 1
    })


# =========================================================
# CONTINUOUS PROCTORING
# =========================================================

@proctoring_bp.route(
    '/api/proctoring/frame',
    methods=['POST']
)
def process_frame():

    if 'user_id' not in session:
        return jsonify({
            "status": "error",
            "message": "Unauthorized or inactive examination session."
        }), 401

    user_id = session["user_id"]
    session_id = session.get("current_exam_session_id") or session.get("current_session_id")
    if not session_id:
        return jsonify({
            "status": "error",
            "message": "Unauthorized or inactive examination session."
        }), 401

    data = request.get_json(silent=True) or {}

    frame_data = data.get("frame")

    if not frame_data:

        return jsonify({
            "status": "error",
            "message": "No frame data received."
        }), 400

    frame_np = decode_base64_frame(frame_data)

    if frame_np is None:

        return jsonify({
            "status": "error",
            "message": "Invalid frame data."
        }), 400

    try:

        face_status, _, face_count = (
            face_detector.detect_faces(frame_np)
        )

        phone_result = object_detector.detect_phone(frame_np, int(session_id))
        phone_detected = bool(phone_result.get("confirmed"))

        conn = DatabaseService.get_connection()
        try:
            response = decision_engine.evaluate_frame(
                conn,
                session_id,
                face_count,
                face_status,
                phone_detected
            )
        finally:
            conn.close()

        response["should_terminate"] = response.get("action") == "TERMINATE"
        response["termination_reason"] = response.get("reason")
        response["integrity_score"] = DatabaseService.get_integrity_score(session_id)

        response.update({
            "face_status": face_status,
            "detected_faces": face_count,
            "phone_detected": phone_detected
        })
        response["phone_detection"] = {**phone_result, "evidence": _save_phone_evidence(session_id, frame_np, phone_result)}

        if response.get("should_terminate"):
            reason = response.get("termination_reason", "Security violation.")
            DatabaseService.update_session_status(session_id, "TERMINATED", reason)
            DatabaseService.save_exam_submission(
                user_id=int(user_id),
                exam_id=int(DatabaseService.get_exam_session(session_id)["exam_id"]),
                session_id=int(session_id),
                score=0,
                total=0,
                percentage=0.0,
                integrity_score=DatabaseService.get_integrity_score(session_id),
                violations=DatabaseService.get_total_violation_count(session_id),
                status="TERMINATED",
                termination_reason=reason
            )

        return jsonify(response)

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================================================
# BROWSER SECURITY EVENTS
# =========================================================

@proctoring_bp.route(
    '/api/proctoring/browser-event',
    methods=['POST']
)
@proctoring_bp.route(
    '/api/log_browser_event',
    methods=['POST']
)
def handle_browser_event():

    if 'user_id' not in session:
        return jsonify({
            "status": "error",
            "message": "Unauthorized or inactive session."
        }), 401

    data = request.get_json(silent=True) or {}

    session_id = data.get(
        "session_id",
        session.get("current_exam_session_id") or session.get("current_session_id")
    )

    event_type = data.get("event_type")

    if not event_type:

        return jsonify({
            "status": "error",
            "message": "Event type is missing."
        }), 400

    event_type = IntegrityEngine.normalize_event_type(event_type)
    exam_session = DatabaseService.get_exam_session(session_id)
    if not exam_session or int(exam_session.get("candidate_id", -1)) != int(session["user_id"]):
        return jsonify({"status": "error", "message": "Invalid examination session."}), 403
    if exam_session.get("status") != "ACTIVE":
        return jsonify({"status": "ignored", "message": "The examination session is no longer active."}), 409

    occurrence_count = DatabaseService.get_violation_count(session_id, event_type) + 1
    response = decision_engine.evaluate_browser_event(
        event_type,
        occurrence_count
    )
    response["should_terminate"] = response.get("action") == "TERMINATE"

    if response.get("deduction", 0):
        response["current_integrity_score"] = DatabaseService.log_suspicious_event(
            session_id,
            event_type,
            "HIGH" if response.get("should_terminate") else "MEDIUM",
            data.get("details", "") or response.get("message", ""),
            response["deduction"],
            data.get("event_id")
        )
    else:
        DatabaseService.log_browser_event(
            session_id,
            event_type,
            data.get("details", ""),
            data.get("event_id")
        )
        response["current_integrity_score"] = DatabaseService.get_integrity_score(session_id)

    if response.get("should_terminate"):

        conn = sqlite3.connect(DB_PATH)

        try:

            cursor = conn.cursor()

            cursor.execute("""
                UPDATE exam_sessions
                SET
                    status = 'TERMINATED',
                    termination_reason = ?
                WHERE id = ?
            """, (
                    response.get(
                        "reason",
                    "Browser security violation."
                ),
                session_id
            ))

            conn.commit()

        finally:

            conn.close()

        DatabaseService.save_exam_submission(
            user_id=int(session["user_id"]),
            exam_id=int(exam_session["exam_id"]),
            session_id=int(session_id),
            score=0,
            total=0,
            percentage=0.0,
            integrity_score=DatabaseService.get_integrity_score(int(session_id)),
            violations=DatabaseService.get_total_violation_count(int(session_id)),
            status="TERMINATED",
            termination_reason=response.get("reason") or "Browser security violation."
        )
        session.pop("current_session_id", None)
        session.pop("current_exam_session_id", None)

    return jsonify(response)