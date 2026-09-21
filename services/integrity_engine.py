import sqlite3

class IntegrityEngine:
    PENALTIES = {
        'TAB_SWITCH': 5,
        'FULLSCREEN_EXIT': 5,
        'FOCUS_LOSS': 3,
        'FACE_ABSENT': 10,
        'MULTIPLE_FACE': 20,
        'PHONE_DETECTED': 20,
        'COPY': 5,
        'CUT': 5,
        'PASTE': 5,
        'CONTEXT_MENU': 5
    }

    EVENT_ALIASES = {
        'TAB_SWITCH': 'TAB_SWITCH',
        'FULLSCREEN_EXIT': 'FULLSCREEN_EXIT',
        'FOCUS_LOSS': 'FOCUS_LOSS',
        'WINDOW_BLUR': 'FOCUS_LOSS',
        'FACE_ABSENT': 'FACE_ABSENT',
        'NO_FACE': 'FACE_ABSENT',
        'NO_FACE_10S': 'FACE_ABSENT',
        'NO_FACE_WARNING': 'FACE_ABSENT',
        'MULTIPLE_FACE': 'MULTIPLE_FACE',
        'MULTIPLE_FACES': 'MULTIPLE_FACE',
        'PHONE_DETECTED': 'PHONE_DETECTED',
        'COPY': 'COPY',
        'COPY_ATTEMPT': 'COPY',
        'PASTE': 'PASTE',
        'PASTE_ATTEMPT': 'PASTE',
        'CUT': 'CUT',
        'CUT_ATTEMPT': 'CUT',
        'CONTEXT_MENU': 'CONTEXT_MENU',
    }

    @classmethod
    def normalize_event_type(cls, event_type):
        value = str(event_type or '').strip().upper()
        return cls.EVENT_ALIASES.get(value, value)

    @classmethod
    def event_aliases(cls, event_type):
        canonical = cls.normalize_event_type(event_type)
        return [alias for alias, target in cls.EVENT_ALIASES.items() if target == canonical]

    @staticmethod
    def get_current_score(conn, session_id):
        cursor = conn.cursor()
        cursor.execute('SELECT score_after FROM integrity_reports WHERE session_id = ? ORDER BY id DESC LIMIT 1', (session_id,))
        row = cursor.fetchone()
        return row['score_after'] if row else 100

    @classmethod
    def apply_penalty(cls, conn, session_id, event_type):
        event_type = cls.normalize_event_type(event_type)
        penalty = cls.PENALTIES.get(event_type, 5)
        current_score = cls.get_current_score(conn, session_id)
        new_score = max(0, current_score - penalty)

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO integrity_reports (session_id, event_type, penalty, score_after)
            VALUES (?, ?, ?, ?)
        ''', (session_id, event_type, penalty, new_score))
        
        cursor.execute('''
            INSERT INTO suspicious_events (session_id, event_type, details)
            VALUES (?, ?, ?)
        ''', (session_id, event_type, f"Deducted {penalty} points. New score: {new_score}"))

        cursor.execute('''
            UPDATE exam_sessions
            SET integrity_score = ?
            WHERE id = ?
        ''', (new_score, session_id))

        session_row = cursor.execute(
            "SELECT user_id, exam_id FROM exam_sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        if session_row:
            cursor.execute('''
                INSERT INTO proctoring_logs
                    (session_id, user_id, exam_id, event_type, severity, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                session_id,
                session_row['user_id'],
                session_row['exam_id'],
                event_type,
                'HIGH' if event_type in ('PHONE_DETECTED', 'MULTIPLE_FACE', 'FACE_ABSENT') else 'MEDIUM',
                f'Deducted {penalty} points. New score: {new_score}'
            ))
        
        conn.commit()
        return new_score

    @staticmethod
    def calculate_risk_level(score, is_terminated=False):
        if score < 60:
            return "High"
        if score < 85:
            return "Medium"
        return "Low"