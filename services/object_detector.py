"""Optional YOLO cell-phone detector with confirmation and incident debouncing."""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from config import Config

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


class ObjectDetector:
    def __init__(self):
        self.model_path = Path(Config.PHONE_MODEL_PATH).resolve()
        self.confidence_threshold = Config.PHONE_CONFIDENCE_THRESHOLD
        self.confirmation_frames = max(1, Config.PHONE_CONFIRMATION_FRAMES)
        self.cooldown_seconds = max(0.0, Config.PHONE_EVENT_COOLDOWN)
        self.model = None
        self.is_active = False
        self.detector_type = "YOLO"
        self._state: Dict[int, Dict[str, Any]] = {}

        if not Config.PHONE_DETECTION_ENABLED:
            print("[PhoneDetector] Phone detection disabled by PHONE_DETECTION_ENABLED.")
            return
        if YOLO is None:
            print(f"[PhoneDetector] Phone detection model unavailable: install ultralytics; expected {self.model_path}")
            return
        if not self.model_path.is_file():
            print(f"[PhoneDetector] Phone detection model unavailable: {self.model_path}")
            return
        try:
            self.model = YOLO(str(self.model_path))
            self.is_active = True
            print(f"[PhoneDetector] detector=YOLO model={self.model_path} loaded=True confidence={self.confidence_threshold}")
        except Exception as exc:
            print(f"[PhoneDetector] Phone detection model unavailable: {exc}")

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "detector_type": self.detector_type,
            "model_path": str(self.model_path),
            "model_loaded": self.is_active,
            "confidence_threshold": self.confidence_threshold,
            "confirmation_frames": self.confirmation_frames,
            "event_cooldown_seconds": self.cooldown_seconds,
        }

    def detect_phone(self, image, session_id: Optional[int] = None) -> Dict[str, Any]:
        result = {
            "model_loaded": self.is_active,
            "phone_detected": False,
            "confirmed": False,
            "confidence": 0.0,
            "bbox": None,
            "status": "active" if self.is_active else "unavailable",
        }
        if not self.is_active or image is None:
            return result

        try:
            predictions = self.model.predict(
                source=image,
                conf=self.confidence_threshold,
                verbose=False,
                device="cpu",
            )
            best = self._best_phone_prediction(predictions)
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            return result

        state_key = int(session_id or 0)
        state = self._state.setdefault(state_key, {"consecutive": 0, "incident_active": False, "last_confirmed": 0.0})
        if best is None:
            state["consecutive"] = 0
            state["incident_active"] = False
            return result

        confidence, bbox = best
        result.update({"phone_detected": True, "confidence": confidence, "bbox": bbox})
        state["consecutive"] += 1
        now = time.time()
        cooldown_elapsed = now - float(state["last_confirmed"] or 0) >= self.cooldown_seconds
        if state["consecutive"] >= self.confirmation_frames and not state["incident_active"] and cooldown_elapsed:
            state["incident_active"] = True
            state["last_confirmed"] = now
            result["confirmed"] = True
        return result

    @staticmethod
    def _best_phone_prediction(predictions):
        best = None
        for prediction in predictions or []:
            names = prediction.names or {}
            boxes = getattr(prediction, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0])
                label = str(names.get(class_id, "")).lower().strip()
                if label not in {"cell phone", "mobile phone", "phone"}:
                    continue
                confidence = float(box.conf[0])
                coordinates = [round(float(value), 2) for value in box.xyxy[0].tolist()]
                if best is None or confidence > best[0]:
                    best = (confidence, coordinates)
        return best
