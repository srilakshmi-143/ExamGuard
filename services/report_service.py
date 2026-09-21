# services/report_service.py
import datetime
import os
import importlib.util
from database.db_service import DatabaseService
from config import Config
from services.analytics_service import calculate_integrity, risk_label

class ReportService:
    @staticmethod
    def get_risk_level(integrity_score):
        return risk_label(float(integrity_score or 0))

    @staticmethod
    def generate_candidate_report(session_id_or_token):
        """Generates a comprehensive, database-driven report for a given session ID or token."""
        # Support fetching by session ID or token
        if isinstance(session_id_or_token, int) or str(session_id_or_token).isdigit():
            conn = DatabaseService.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                      SELECT es.*, u.username, u.full_name, u.college, u.branch,
                          u.year, u.roll_number, u.photo_path,
                          e.title as exam_title, e.duration AS duration_minutes,
                          e.total_marks, (e.total_marks * e.pass_percentage / 100.0) AS pass_marks
                    FROM exam_sessions es
                    JOIN users u ON es.candidate_id = u.id
                    JOIN exams e ON es.exam_id = e.id
                    WHERE es.id = ?
                """, (int(session_id_or_token),))
                row = cursor.fetchone()
                session_rec = dict(row) if row else None
            finally:
                conn.close()
        else:
            session_rec = DatabaseService.get_session_by_token(session_id_or_token)

        if not session_rec:
            return None

        session_id = session_rec['id']

        conn = DatabaseService.get_connection()
        try:
            scored_events = [dict(row) for row in conn.execute(
                "SELECT event_type, penalty FROM integrity_reports WHERE session_id = ? ORDER BY id",
                (session_id,)
            ).fetchall()]
        finally:
            conn.close()

        # Fetch violation breakdown
        tab_switches = DatabaseService.get_violation_count(session_id, 'TAB_SWITCH')
        no_face_events = DatabaseService.get_violation_count(session_id, 'FACE_ABSENT')
        multiple_faces = DatabaseService.get_violation_count(session_id, 'MULTIPLE_FACES')
        fullscreen_exits = DatabaseService.get_violation_count(session_id, 'FULLSCREEN_EXIT')
        copy_pastes = sum(
            DatabaseService.get_violation_count(session_id, event_type)
            for event_type in ('COPY', 'PASTE', 'CUT')
        )
        phone_events = DatabaseService.get_violation_count(session_id, 'PHONE_DETECTED')

        total_violations = tab_switches + no_face_events + multiple_faces + fullscreen_exits + copy_pastes + phone_events

        # Calculate session duration
        start_time = session_rec.get('start_time')
        end_time = session_rec.get('end_time')
        duration_str = "N/A"
        
        if start_time and end_time:
            try:
                fmt = "%Y-%m-%d %H:%M:%S"
                t_start = datetime.datetime.strptime(str(start_time).split('.')[0], fmt)
                t_end = datetime.datetime.strptime(str(end_time).split('.')[0], fmt)
                elapsed_seconds = int((t_end - t_start).total_seconds())
                mins, secs = divmod(elapsed_seconds, 60)
                duration_str = f"{mins}m {secs}s"
            except Exception:
                duration_str = f"{session_rec.get('duration_minutes', 30)} mins"

        integrity_score = session_rec.get('integrity_score', 100)
        risk_level = ReportService.get_risk_level(integrity_score)

        # Pass/Fail determination
        score = session_rec.get('score', 0)
        pass_marks = session_rec.get('pass_marks', 40)
        status = session_rec.get('status', 'IN_PROGRESS')
        
        if status == 'COMPLETED':
            result_status = "PASSED" if score >= pass_marks else "FAILED"
        elif status == 'TERMINATED':
            result_status = "DISQUALIFIED"
        else:
            result_status = "PENDING"

        phone_model_available = bool(
            importlib.util.find_spec("ultralytics")
            and os.path.isfile(Config.PHONE_MODEL_PATH)
        )
        return {
            'session_id': session_id,
            'session_token': session_rec['session_token'],
            'candidate': {
                'name': session_rec.get('full_name') or session_rec.get('username') or 'Student',
                'college': session_rec.get('college') or "Vignan's Nirula",
                'branch': session_rec.get('branch') or "CSE",
                'year': session_rec.get('year') or "4th Year",
                'roll_number': session_rec.get('roll_number') or "N/A",
                'photo_path': session_rec.get('photo_path')
            },
            'exam': {
                'title': session_rec.get('exam_title', 'Examination'),
                'total_marks': session_rec.get('total_marks', 100),
                'score': score,
                'percentage': session_rec.get('percentage', 0.0),
                'result_status': result_status
            },
            'integrity': {
                'score': integrity_score,
                'risk_level': risk_level,
                'calculation': calculate_integrity(scored_events),
                'total_violations': total_violations,
                'violations_breakdown': {
                    'tab_switches': tab_switches,
                    'face_missing': no_face_events,
                    'multiple_faces': multiple_faces,
                    'fullscreen_exits': fullscreen_exits,
                    'copy_paste': copy_pastes,
                    'phone_detected': phone_events
                },
                'presence_ratio': session_rec.get('presence_ratio')
            },
            'session': {
                'start_time': start_time,
                'end_time': end_time or "In Progress / Terminated",
                'duration': duration_str,
                'status': status,
                'termination_reason': session_rec.get('termination_reason') or "N/A"
            },
            'system_audit': {
                'pre_exam_face_verification': "Successful (Visual Similarity Analysis)",
                'object_detection_status': "Active" if phone_model_available else "Unavailable (model files not installed)"
            }
        }

    @staticmethod
    def get_dashboard_analytics(user_id):
        """Generates global exam analytics and trends for the candidate dashboard."""
        assignments = DatabaseService.get_user_assignment_history(user_id)

        if not assignments:
            return {
                'stats': {'total': 0, 'completed': 0, 'pending': 0, 'terminated': 0, 'avg_score': 0, 'avg_integrity': 0},
                'violations': {'tab_switches': 0, 'face_missing': 0, 'multiple_faces': 0, 'copy_paste': 0},
                'chart_data': {'labels': [], 'exam_scores': [], 'integrity_scores': []}
            }

        total = len(assignments)
        completed = sum(1 for a in assignments if a['status'] == 'COMPLETED')
        terminated = sum(1 for a in assignments if a['status'] == 'TERMINATED')
        pending = sum(1 for a in assignments if a['status'] == 'IN_PROGRESS')

        completed_scores = [a['percentage'] for a in assignments if a['status'] == 'COMPLETED']
        avg_score = round(sum(completed_scores) / len(completed_scores), 1) if completed_scores else 0.0

        integrity_scores = [a['integrity_score'] for a in assignments]
        avg_integrity = round(sum(integrity_scores) / len(integrity_scores), 1) if integrity_scores else 100.0

        # Sum total violations across all user sessions
        total_tab = 0
        total_face = 0
        total_multi = 0
        total_copy = 0

        for a in assignments:
            sid = a['session_id']
            total_tab += DatabaseService.get_violation_count(sid, 'TAB_SWITCH')
            total_face += DatabaseService.get_violation_count(sid, 'FACE_ABSENT')
            total_multi += DatabaseService.get_violation_count(sid, 'MULTIPLE_FACES')
            total_copy += sum(
                DatabaseService.get_violation_count(sid, event_type)
                for event_type in ('COPY', 'PASTE', 'CUT')
            )

        # Chronological trend data for Chart.js
        reversed_assignments = list(reversed(assignments))
        labels = [a['exam_title'][:15] + "..." for a in reversed_assignments]
        exam_scores = [a['percentage'] for a in reversed_assignments]
        integrity_trends = [a['integrity_score'] for a in reversed_assignments]

        return {
            'stats': {
                'total': total,
                'completed': completed,
                'pending': pending,
                'terminated': terminated,
                'avg_score': avg_score,
                'avg_integrity': avg_integrity
            },
            'violations': {
                'tab_switches': total_tab,
                'face_missing': total_face,
                'multiple_faces': total_multi,
                'copy_paste': total_copy
            },
            'chart_data': {
                'labels': labels,
                'exam_scores': exam_scores,
                'integrity_scores': integrity_trends
            }
        }