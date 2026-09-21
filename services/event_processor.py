from database.db_service import DatabaseService
from services.decision_engine import DecisionEngine

class EventProcessor:
    """
    Orchestrates the ingestion, logging, integrity updating, and enforcement of security events.
    """
    @staticmethod
    def process_event(session_id, event_type, details="", session_context=None):
        if session_context is None:
            session_context = {}

        if event_type == "TAB_SWITCH":
            session_context["tab_switch_count"] = DatabaseService.get_tab_switch_count(session_id)

        # Log raw browser event
        DatabaseService.log_browser_event(session_id, event_type, details)

        # Evaluate decision
        decision = DecisionEngine.evaluate_event(event_type, session_context)

        # Log suspicious event if deduction or enforcement applies
        new_score = DatabaseService.get_integrity_score(session_id)
        if decision["deduction"] > 0 or decision["action"] != "ALLOW":
            new_score = DatabaseService.log_suspicious_event(
                session_id=session_id,
                event_type=event_type,
                severity="HIGH" if decision["action"] == "TERMINATE" else "MEDIUM",
                description=decision["message"],
                deduction=decision["deduction"]
            )

        # Apply termination if decision engine dictates
        if decision["action"] == "TERMINATE":
            DatabaseService.update_session_status(session_id, "TERMINATED", decision["message"])

        return {
            "action": decision["action"],
            "message": decision["message"],
            "current_integrity_score": new_score
        }