"""Deterministic session-behaviour clustering for invigilator analytics."""

from typing import Any, Dict, List

from database.db_service import DatabaseService
from services.integrity_engine import IntegrityEngine

try:
    import pandas as pd
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
except ImportError:
    pd = None
    KMeans = None
    StandardScaler = None

FEATURES = [
    "integrity_score", "tab_switch_count", "focus_loss_count",
    "face_absence_count", "face_absence_duration", "fullscreen_exit_count",
    "copy_paste_count", "multiple_face_count", "phone_detection_count",
]


class KMeansService:
    @classmethod
    def get_session_data(cls) -> List[Dict[str, Any]]:
        conn = DatabaseService.get_connection()
        try:
            rows = conn.execute("""
                SELECT id AS session_id, user_id, exam_id,
                       COALESCE(integrity_score, 100) AS integrity_score,
                       COALESCE(status, 'ACTIVE') AS status
                FROM exam_sessions ORDER BY id
            """).fetchall()
            sessions = [dict(row) for row in rows]
            for item in sessions:
                event_rows = conn.execute("""
                    SELECT event_type, COUNT(*) AS count
                    FROM proctoring_logs WHERE session_id = ? GROUP BY event_type
                """, (item["session_id"],)).fetchall()
                counts = {}
                for row in event_rows:
                    event_type = IntegrityEngine.normalize_event_type(row["event_type"])
                    counts[event_type] = counts.get(event_type, 0) + int(row["count"])
                interval_row = conn.execute("""
                    SELECT COALESCE(SUM(duration_seconds), 0) AS duration
                    FROM face_absence_intervals WHERE session_id = ?
                """, (item["session_id"],)).fetchone()
                item.update({
                    "tab_switch_count": counts.get("TAB_SWITCH", 0),
                    "focus_loss_count": counts.get("FOCUS_LOSS", 0),
                    "face_absence_count": counts.get("FACE_ABSENT", 0),
                    "face_absence_duration": float(interval_row["duration"] or 0),
                    "fullscreen_exit_count": counts.get("FULLSCREEN_EXIT", 0),
                    "copy_paste_count": sum(counts.get(name, 0) for name in ("COPY", "PASTE", "CUT")),
                    "multiple_face_count": counts.get("MULTIPLE_FACE", 0),
                    "phone_detection_count": counts.get("PHONE_DETECTED", 0),
                })
            return sessions
        finally:
            conn.close()

    @classmethod
    def analyze(cls) -> Dict[str, Any]:
        sessions = cls.get_session_data()
        if not sessions:
            return {"total_sessions": 0, "clusters": [], "message": "No session data available for analysis."}
        if pd is None or KMeans is None or StandardScaler is None:
            return {"total_sessions": len(sessions), "clusters": [], "message": "Install pandas and scikit-learn to enable K-Means clustering."}
        frame = pd.DataFrame(sessions).fillna(0)
        if len(frame) < 2:
            return {"total_sessions": len(sessions), "clusters": [], "message": "At least two sessions are required for clustering."}
        cluster_count = min(3, len(frame))
        scaled = StandardScaler().fit_transform(frame[FEATURES].astype(float))
        model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
        frame["cluster"] = model.fit_predict(scaled)
        frame["risk_label"] = frame.apply(cls._risk_label, axis=1)
        profiles = []
        for cluster_id, group in frame.groupby("cluster"):
            profiles.append({
                "cluster": int(cluster_id),
                "sessions": int(len(group)),
                "average_integrity": round(float(group["integrity_score"].mean()), 2),
                "average_violations": round(float(group[FEATURES[1:]].sum(axis=1).mean()), 2),
                "risk_label": cls._risk_label(group.mean(numeric_only=True)),
            })
        return {
            "total_sessions": len(sessions),
            "clusters": profiles,
            "assignments": frame[["session_id", "cluster", "risk_label"]].to_dict("records"),
            "features": FEATURES,
        }

    @staticmethod
    def _risk_label(row: Any) -> str:
        score = float(row.get("integrity_score", 100) or 100)
        violations = sum(float(row.get(name, 0) or 0) for name in FEATURES[1:])
        if score < 60 or violations >= 6:
            return "High"
        if score < 85 or violations >= 2:
            return "Medium"
        return "Low"
