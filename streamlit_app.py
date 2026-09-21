"""Optional invigilator dashboard.

Run with: streamlit run streamlit_app.py
Candidate-facing Flask routes remain the system of record.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from database.db_service import DatabaseService
from services.ai_report_service import generate_integrity_report
from services.analytics_service import cohort_risk_profile
from services.kmeans_service import KMeansService
from services.report_service import ReportService

st.set_page_config(page_title="ExamGuard Invigilator Dashboard", layout="wide")
st.title("ExamGuard | Invigilator Dashboard")
st.caption("Authorized monitoring and integrity analytics")

users = DatabaseService.get_all_users()
if not users:
    st.info("No candidate data is available.")
else:
    conn = DatabaseService.get_connection()
    try:
        summary = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active,
                   SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status = 'TERMINATED' THEN 1 ELSE 0 END) AS terminated,
                   AVG(COALESCE(integrity_score, 100)) AS average_integrity
            FROM exam_sessions
        """).fetchone()
        sessions = [dict(row) for row in conn.execute("""
                 SELECT es.id, es.user_id, es.exam_id, u.username, e.title, es.status,
                     es.integrity_score, es.presence_ratio, es.score, es.percentage
            FROM exam_sessions es
            LEFT JOIN users u ON u.id = es.candidate_id
            LEFT JOIN exams e ON e.id = es.exam_id
            ORDER BY es.id DESC
        """).fetchall()]
        event_rows = [dict(row) for row in conn.execute("""
            SELECT session_id, event_type, severity, details, timestamp
            FROM proctoring_logs ORDER BY timestamp DESC
        """).fetchall()]
    finally:
        conn.close()
    cols = st.columns(5)
    labels = [("Sessions", summary["total"] or 0), ("Active", summary["active"] or 0), ("Completed", summary["completed"] or 0), ("Flagged", summary["terminated"] or 0), ("Avg integrity", round(summary["average_integrity"] or 0, 1))]
    for col, (label, value) in zip(cols, labels):
        col.metric(label, value)
    st.subheader("Live and completed sessions")
    frame = pd.DataFrame(sessions)
    candidate_filter = st.selectbox("Candidate", ["All"] + sorted(frame["username"].fillna("Unknown").unique().tolist()))
    exam_filter = st.selectbox("Exam", ["All"] + sorted(frame["title"].fillna("Unknown").unique().tolist()))
    filtered = frame.copy()
    if candidate_filter != "All":
        filtered = filtered[filtered["username"].fillna("Unknown") == candidate_filter]
    if exam_filter != "All":
        filtered = filtered[filtered["title"].fillna("Unknown") == exam_filter]
    st.dataframe(filtered, use_container_width=True)
    if not filtered.empty:
        st.subheader("Integrity score distribution")
        st.bar_chart(filtered["integrity_score"].fillna(0).value_counts().sort_index())
        figure, axis = plt.subplots(figsize=(7, 3.5))
        sns.histplot(filtered["integrity_score"].fillna(0), bins=10, ax=axis)
        axis.set_xlabel("Integrity score")
        axis.set_ylabel("Sessions")
        st.pyplot(figure, clear_figure=True)

    st.subheader("Suspicious event heatmap")
    selected_ids = set(filtered["id"].astype(int).tolist()) if not filtered.empty else set()
    selected_events = [row for row in event_rows if int(row["session_id"]) in selected_ids]
    if selected_events:
        event_frame = pd.DataFrame(selected_events)
        matrix = pd.crosstab(event_frame["event_type"], event_frame["session_id"])
        figure, axis = plt.subplots(figsize=(9, 4.5))
        sns.heatmap(matrix, annot=True, fmt="d", cmap="YlOrRd", ax=axis)
        axis.set_xlabel("Session")
        axis.set_ylabel("Event")
        st.pyplot(figure, clear_figure=True)
        st.dataframe(event_frame, use_container_width=True)
    else:
        st.info("No suspicious events match the selected filters.")

    st.subheader("Cohort risk profile")
    st.dataframe(cohort_risk_profile(sessions), use_container_width=True)

    st.subheader("AI integrity summaries")
    for session in filtered.head(10).to_dict("records"):
        report = ReportService.generate_candidate_report(int(session["id"]))
        if report:
            st.write(f"Session {session['id']} | {report['session']['status']}")
            st.write(generate_integrity_report({**report, "events": [row for row in event_rows if row["session_id"] == session["id"]]}))

    st.subheader("Alerts and evidence")
    with DatabaseService.get_connection() as evidence_conn:
        evidence = [dict(row) for row in evidence_conn.execute("SELECT * FROM evidence ORDER BY timestamp DESC").fetchall()]
    st.dataframe(evidence, use_container_width=True)
    st.subheader("Behaviour clustering")
    st.json(KMeansService.analyze())
