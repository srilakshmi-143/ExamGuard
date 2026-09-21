import time
from datetime import datetime

from config import Config
from services.integrity_engine import IntegrityEngine
from services import presence_tracker

# Persistent in-memory tracking for wall-clock time missing timers
NO_FACE_TIMERS = {}
FACE_ABSENT_CONFIRMED = set()
FACE_ABSENT_TERMINATED = set()
VIOLATION_COOLDOWNS = {}

FACE_ABSENCE_THRESHOLD_SECONDS = float(getattr(Config, "FACE_ABSENCE_THRESHOLD_SECONDS", 2.0))
FACE_ABSENCE_TERMINATION_SECONDS = float(getattr(Config, "FACE_ABSENCE_TERMINATION_SECONDS", 10.0))


def _record_face_interval(conn, session_id, started_at, ended_at):
    if started_at is None or ended_at is None:
        return
    duration = max(0.0, ended_at - started_at)
    conn.execute("""
        INSERT INTO face_absence_intervals (session_id, absent_start, absent_end, duration_seconds)
        VALUES (?, ?, ?, ?)
    """, (
        session_id,
        datetime.utcfromtimestamp(started_at).strftime("%Y-%m-%d %H:%M:%S"),
        datetime.utcfromtimestamp(ended_at).strftime("%Y-%m-%d %H:%M:%S"),
        round(duration, 2)
    ))
    conn.commit()


def _apply_event_penalty(conn, session_id, event_type, cooldown_seconds=5.0):
    now = time.time()
    key = (session_id, event_type)
    last_applied = VIOLATION_COOLDOWNS.get(key, 0.0)
    if now - last_applied < cooldown_seconds:
        return IntegrityEngine.get_current_score(conn, session_id)
    VIOLATION_COOLDOWNS[key] = now
    return IntegrityEngine.apply_penalty(conn, session_id, event_type)


class DecisionEngine:
    @staticmethod
    def evaluate_event(event_type, session_context=None):
        session_context = session_context or {}
        return DecisionEngine.evaluate_browser_event(
            event_type,
            session_context.get("tab_switch_count", 0)
        )

    @staticmethod
    def evaluate_browser_event(event_type, occurrence_count=0):
        """Evaluate browser security events using the existing integrity rules."""
        event_type = IntegrityEngine.normalize_event_type(event_type)
        threshold_events = {"TAB_SWITCH", "FULLSCREEN_EXIT"}
        deductions = {
            "TAB_SWITCH": 5,
            "FULLSCREEN_EXIT": 5,
            "FOCUS_LOSS": 3,
            "FACE_ABSENT": 10,
            "MULTIPLE_FACE": 20,
            "PHONE_DETECTED": 20,
            "COPY": 5,
            "PASTE": 5,
            "CUT": 5,
            "CONTEXT_MENU": 5
        }
        should_terminate = event_type in threshold_events and occurrence_count >= 3
        deduction = deductions.get(event_type, 0)
        if event_type == "TAB_SWITCH":
            message = (
                f"Tab switch warning {occurrence_count} of 3. Please remain on the examination page."
                if not should_terminate else "Exam terminated after 3 tab-switch violations."
            )
            reason = "Exam terminated after 3 tab-switch violations." if should_terminate else ""
        elif event_type == "FULLSCREEN_EXIT":
            message = (
                f"Fullscreen exit warning {occurrence_count} of 3. Please return to fullscreen mode."
                if not should_terminate else "Exam terminated after 3 fullscreen violations."
            )
            reason = "Exam terminated after 3 fullscreen violations." if should_terminate else ""
        else:
            message = "Browser security violation recorded."
            reason = ""
        return {
            "action": "TERMINATE" if should_terminate else "CONTINUE",
            "message": message,
            "reason": reason,
            "deduction": deduction,
            "occurrence_count": occurrence_count
        }

    @staticmethod
    def evaluate_frame(conn, session_id, face_count, face_status, phone_detected=False):
        current_time = time.time()
        presence_tracker.observe(session_id, face_count == 1, current_time)
        score = IntegrityEngine.get_current_score(conn, session_id)

        # 1. Phone Detection Evaluation
        if phone_detected:
            score = _apply_event_penalty(conn, session_id, 'PHONE_DETECTED')
            return {
                'action': 'TERMINATE',
                'reason': 'Exam terminated: Mobile phone device detected in camera feed.',
                'integrity_score': score,
                'face_count': face_count
            }

        # 2. Multiple Face Detection Evaluation
        if face_count > 1:
            score = _apply_event_penalty(conn, session_id, 'MULTIPLE_FACE')
            return {
                'action': 'TERMINATE',
                'reason': 'Exam terminated: Multiple faces detected in camera view.',
                'integrity_score': score,
                'face_count': face_count
            }

        # 3. No Face Continuous Time Evaluation
        if face_count == 0:
            if session_id not in NO_FACE_TIMERS:
                NO_FACE_TIMERS[session_id] = current_time
                FACE_ABSENT_CONFIRMED.discard(session_id)
                FACE_ABSENT_TERMINATED.discard(session_id)

            elapsed = current_time - NO_FACE_TIMERS[session_id]
            missing_seconds = round(elapsed, 1)

            if elapsed >= FACE_ABSENCE_THRESHOLD_SECONDS:
                if session_id not in FACE_ABSENT_CONFIRMED:
                    FACE_ABSENT_CONFIRMED.add(session_id)
                    score = IntegrityEngine.apply_penalty(conn, session_id, 'FACE_ABSENT')
                    return {
                        'action': 'WARNING',
                        'reason': f'Face absent for {missing_seconds}s. Integrity penalty applied once for this absence interval.',
                        'integrity_score': score,
                        'face_count': 0,
                        'missing_seconds': missing_seconds,
                        'face_absent_confirmed': True,
                    }

                if elapsed >= FACE_ABSENCE_TERMINATION_SECONDS and session_id not in FACE_ABSENT_TERMINATED:
                    FACE_ABSENT_TERMINATED.add(session_id)
                    started_at = NO_FACE_TIMERS.pop(session_id, None)
                    _record_face_interval(conn, session_id, started_at, current_time)
                    presence = presence_tracker.finalize(session_id, current_time)
                    conn.execute(
                        "UPDATE exam_sessions SET presence_ratio = ? WHERE id = ?",
                        (presence["presence_ratio"], session_id),
                    )
                    conn.commit()
                    return {
                        'action': 'TERMINATE',
                        'reason': 'Exam terminated: Candidate face missing continuously for 10 seconds.',
                        'integrity_score': score,
                        'face_count': 0,
                        'missing_seconds': missing_seconds,
                        'face_absent_confirmed': True,
                        'presence_ratio': presence['presence_ratio'],
                    }

                return {
                    'action': 'WARNING',
                    'reason': f'Face absent for {missing_seconds}s. Monitoring continues.',
                    'integrity_score': score,
                    'face_count': 0,
                    'missing_seconds': missing_seconds,
                    'face_absent_confirmed': True,
                }

            return {
                'action': 'WARNING',
                'reason': f'Warning: Face not detected! ({missing_seconds}s / {FACE_ABSENCE_THRESHOLD_SECONDS:.1f}s)',
                'integrity_score': score,
                'face_count': 0,
                'missing_seconds': missing_seconds,
            }

        # Reset timer if face returns
        if session_id in NO_FACE_TIMERS:
            started_at = NO_FACE_TIMERS.pop(session_id)
            _record_face_interval(conn, session_id, started_at, current_time)
            FACE_ABSENT_CONFIRMED.discard(session_id)
            FACE_ABSENT_TERMINATED.discard(session_id)

        return {
            'action': 'CONTINUE',
            'reason': 'Single candidate verified.',
            'integrity_score': score,
            'face_count': 1
        }