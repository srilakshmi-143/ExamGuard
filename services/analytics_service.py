"""Pandas-backed integrity scoring and session analytics."""

from typing import Any, Dict, Iterable, List
from services.integrity_engine import IntegrityEngine

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
except ImportError:
    plt = None
    sns = None


EVENT_WEIGHTS = {
    "TAB_SWITCH": 5,
    "FOCUS_LOSS": 3,
    "FULLSCREEN_EXIT": 5,
    "FACE_ABSENT": 10,
    "MULTIPLE_FACE": 20,
    "PHONE_DETECTED": 20,
    "COPY": 5,
    "PASTE": 5,
    "CUT": 5,
}


def risk_label(score: float) -> str:
    if score < 60:
        return "High"
    if score < 85:
        return "Medium"
    return "Low"


def calculate_integrity(events: Iterable[Dict[str, Any]], starting_score: float = 100) -> Dict[str, Any]:
    records = list(events or [])
    if pd is None:
        deductions = sum(EVENT_WEIGHTS.get(IntegrityEngine.normalize_event_type(item.get("event_type", "")), 0) for item in records)
        score = max(0, min(100, starting_score - deductions))
        return {"integrity_score": round(score, 2), "risk_label": risk_label(score), "event_count": len(records), "weighted_deduction": deductions}
    frame = pd.DataFrame(records)
    if frame.empty:
        return {"integrity_score": float(starting_score), "risk_label": risk_label(starting_score), "event_count": 0, "weighted_deduction": 0}
    frame["event_type"] = frame["event_type"].map(IntegrityEngine.normalize_event_type)
    frame["weight"] = frame["event_type"].map(EVENT_WEIGHTS).fillna(0)
    deduction = float(frame["weight"].sum())
    score = max(0, min(100, float(starting_score) - deduction))
    return {"integrity_score": round(score, 2), "risk_label": risk_label(score), "event_count": int(len(frame)), "weighted_deduction": round(deduction, 2), "event_frequencies": frame["event_type"].value_counts().to_dict()}


def cohort_risk_profile(sessions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate actual session rows into candidate risk cohorts."""
    records = list(sessions or [])
    if pd is None or not records:
        return []
    frame = pd.DataFrame(records)
    if "user_id" not in frame or "integrity_score" not in frame:
        return []
    frame["integrity_score"] = pd.to_numeric(frame["integrity_score"], errors="coerce").fillna(100)
    frame["risk_label"] = frame["integrity_score"].map(risk_label)
    return frame.groupby(["user_id", "risk_label"], as_index=False).agg(
        sessions=("user_id", "size"),
        average_integrity=("integrity_score", "mean"),
    ).assign(average_integrity=lambda value: value["average_integrity"].round(2)).to_dict("records")


def integrity_distribution_figure(sessions: Iterable[Dict[str, Any]]):
    """Return a Matplotlib figure for actual persisted integrity scores."""
    if pd is None or plt is None:
        return None
    frame = pd.DataFrame(list(sessions or []))
    if frame.empty or "integrity_score" not in frame:
        return None
    figure, axis = plt.subplots(figsize=(7, 4))
    sns.histplot(pd.to_numeric(frame["integrity_score"], errors="coerce").fillna(0), bins=10, ax=axis)
    axis.set_title("Integrity score distribution")
    axis.set_xlabel("Integrity score")
    axis.set_ylabel("Sessions")
    figure.tight_layout()
    return figure


def event_heatmap_figure(events: Iterable[Dict[str, Any]]):
    """Return a Seaborn event-by-session heatmap from persisted log rows."""
    if pd is None or plt is None or sns is None:
        return None
    frame = pd.DataFrame(list(events or []))
    if frame.empty or not {"session_id", "event_type"}.issubset(frame.columns):
        return None
    frame["event_type"] = frame["event_type"].map(IntegrityEngine.normalize_event_type)
    matrix = pd.crosstab(frame["event_type"], frame["session_id"])
    figure, axis = plt.subplots(figsize=(9, 5))
    sns.heatmap(matrix, annot=True, fmt="d", cmap="YlOrRd", ax=axis)
    axis.set_title("Suspicious events by session")
    axis.set_xlabel("Session")
    axis.set_ylabel("Event")
    figure.tight_layout()
    return figure
