"""Timestamp-based face presence accounting for active exam sessions."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class _SessionPresence:
    started_at: float
    last_at: float
    last_present: bool
    present_seconds: float = 0.0
    absent_seconds: float = 0.0


_TRACKERS: dict[int, _SessionPresence] = {}


def reset(session_id: int) -> None:
    _TRACKERS.pop(int(session_id), None)


def observe(session_id: int, present: bool, timestamp: Optional[float] = None) -> dict:
    """Record one observation; elapsed time belongs to the preceding state."""
    session_id = int(session_id)
    now = float(timestamp if timestamp is not None else datetime.now(timezone.utc).timestamp())
    tracker = _TRACKERS.get(session_id)
    if tracker is None:
        tracker = _SessionPresence(now, now, bool(present))
        _TRACKERS[session_id] = tracker
        return snapshot(session_id)

    if now < tracker.last_at:
        raise ValueError("Presence timestamps must be monotonic")
    elapsed = now - tracker.last_at
    if tracker.last_present:
        tracker.present_seconds += elapsed
    else:
        tracker.absent_seconds += elapsed
    tracker.last_at = now
    tracker.last_present = bool(present)
    return snapshot(session_id)


def finalize(session_id: int, timestamp: Optional[float] = None) -> dict:
    """Close monitoring at submission or termination and remove live state."""
    session_id = int(session_id)
    if session_id not in _TRACKERS:
        return {"active_seconds": 0.0, "present_seconds": 0.0, "absent_seconds": 0.0, "presence_ratio": None}
    result = observe(session_id, _TRACKERS[session_id].last_present, timestamp)
    _TRACKERS.pop(session_id, None)
    return result


def snapshot(session_id: int) -> dict:
    tracker = _TRACKERS.get(int(session_id))
    if tracker is None:
        return {"active_seconds": 0.0, "present_seconds": 0.0, "absent_seconds": 0.0, "presence_ratio": None}
    active = tracker.present_seconds + tracker.absent_seconds
    ratio = tracker.present_seconds / active if active > 0 else None
    return {
        "active_seconds": round(active, 3),
        "present_seconds": round(tracker.present_seconds, 3),
        "absent_seconds": round(tracker.absent_seconds, 3),
        "presence_ratio": round(ratio, 6) if ratio is not None else None,
    }
