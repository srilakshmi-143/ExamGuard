"""Small admin/invigilator API for reports, analytics, and authorized exports."""

from functools import wraps

from flask import Blueprint, Response, jsonify, session

from database.db_service import DatabaseService
from services.export_service import as_csv, as_json
from services.kmeans_service import KMeansService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        user = DatabaseService.get_user_by_id(user_id) if user_id else None
        if not user or user.get("role") not in ("admin", "invigilator"):
            return jsonify({"status": "error", "message": "Administrator access required."}), 403
        return view(*args, **kwargs)
    return wrapped


@admin_bp.get("/analytics")
@admin_required
def analytics():
    return jsonify(KMeansService.analyze())


@admin_bp.get("/sessions/<int:session_id>/export.json")
@admin_required
def export_json(session_id):
    payload = as_json(session_id)
    if payload is None:
        return jsonify({"status": "error", "message": "Session not found."}), 404
    return Response(payload, mimetype="application/json", headers={"Content-Disposition": f"attachment; filename=session_{session_id}.json"})


@admin_bp.get("/sessions/<int:session_id>/export.csv")
@admin_required
def export_csv(session_id):
    payload = as_csv(session_id)
    if payload is None:
        return jsonify({"status": "error", "message": "Session not found."}), 404
    return Response(payload, mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"})


@admin_bp.get("/sessions/<int:session_id>/evidence")
@admin_required
def evidence(session_id):
    conn = DatabaseService.get_connection()
    try:
        rows = conn.execute("SELECT * FROM evidence WHERE session_id = ? ORDER BY timestamp", (session_id,)).fetchall()
        return jsonify({"session_id": session_id, "evidence": [dict(row) for row in rows]})
    finally:
        conn.close()
