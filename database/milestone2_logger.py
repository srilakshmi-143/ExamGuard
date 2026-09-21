from database.db_service import DatabaseService

def log_proctoring_event(session_id, event_type, details, integrity_impact):
    if DatabaseService.get_exam_session(session_id):
        DatabaseService.log_suspicious_event(
            session_id=session_id,
            event_type=event_type,
            severity="MEDIUM",
            description=details,
            deduction=integrity_impact
        )

def get_current_integrity_score(session_id):
    return DatabaseService.get_integrity_score(session_id)

def terminate_session_in_db(session_id, reason):
    DatabaseService.update_session_status(session_id, "TERMINATED", reason)