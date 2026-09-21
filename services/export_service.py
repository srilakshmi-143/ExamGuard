"""Authorized JSON and CSV exports backed by the canonical SQLite database."""

import csv
import io
import json
from typing import Any, Dict

from database.db_service import DatabaseService
from services.analytics_service import calculate_integrity
from services.kmeans_service import KMeansService
from services.report_service import ReportService
from services.ai_report_service import generate_integrity_report


def session_export(session_id: int) -> Dict[str, Any] | None:
    report = ReportService.generate_candidate_report(session_id)
    if not report:
        return None
    events = DatabaseService.get_proctoring_logs_for_session(session_id)
    # Recompute from the neutral baseline; the persisted session score already
    # includes these events and must not be used as a second starting deduction.
    score = calculate_integrity(events, 100)
    clusters = KMeansService.analyze().get("assignments", [])
    cluster = next((row for row in clusters if int(row["session_id"]) == int(session_id)), None)
    report["events"] = events
    report["integrity"]["risk_label"] = score["risk_label"]
    report["cluster"] = cluster
    report["ai_report"] = generate_integrity_report(report)
    return report


def as_json(session_id: int) -> str | None:
    payload = session_export(session_id)
    return json.dumps(payload, default=str, indent=2) if payload else None


def as_csv(session_id: int) -> str | None:
    payload = session_export(session_id)
    if not payload:
        return None
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["session_id", "event_type", "timestamp", "severity", "details"])
    writer.writeheader()
    for event in payload.get("events", []):
        writer.writerow({key: event.get(key) for key in writer.fieldnames})
    return output.getvalue()
