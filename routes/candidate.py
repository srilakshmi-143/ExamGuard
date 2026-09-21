import sqlite3
from flask import Blueprint, render_template, session, redirect, url_for, flash
from database.db_service import DatabaseService
from config import Config

candidate_bp = Blueprint('candidate', __name__)

@candidate_bp.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('auth.login'))

    # Direct query to ensure exams are retrieved
    try:
        conn = sqlite3.connect(Config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams;")
        available_exams = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print("Database error in candidate dashboard:", e)
        available_exams = DatabaseService.get_all_exams()

    history = DatabaseService.get_user_assignment_history(user_id)

    analytics = {
        'total_exams': len(history),
        'completed': len([h for h in history if h.get('status') == 'COMPLETED']),
        'pending': len([h for h in history if h.get('status') == 'IN_PROGRESS']),
        'terminated': len([h for h in history if h.get('status') == 'TERMINATED']),
        'avg_score': 0,
        'avg_integrity': 100
    }

    # Explicit inline template rendering to bypass template path issues
    return render_template(
        'candidate/dashboard.html',
        exams=available_exams,
        assignments=available_exams,
        history=history,
        analytics=analytics
    )