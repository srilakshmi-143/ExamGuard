import os
import secrets


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Generate an ephemeral development key when none is configured; production
    # deployments must provide SECRET_KEY so sessions survive restarts safely.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # SINGLE DATABASE — do not use examguard.db
    DATABASE_PATH = os.environ.get(
        "EXAMGUARD_DATABASE_PATH",
        os.path.join(BASE_DIR, "database", "exam.db")
    )

    # Upload directories
    UPLOAD_FOLDER = os.path.join(
        BASE_DIR,
        "uploads"
    )

    REGISTRATION_PHOTOS_FOLDER = os.path.join(
        UPLOAD_FOLDER,
        "registration_photos"
    )

    # Haar Cascade
    HAAR_CASCADE_PATH = os.path.join(
        BASE_DIR,
        "services",
        "haarcascade_frontalface_default.xml"
    )

    PHONE_DETECTION_ENABLED = os.environ.get("PHONE_DETECTION_ENABLED", "1").lower() in ("1", "true", "yes")
    PHONE_MODEL_PATH = os.environ.get(
        "PHONE_MODEL_PATH",
        os.path.join(BASE_DIR, "models", "yolo11n.pt")
    )
    PHONE_CONFIDENCE_THRESHOLD = float(os.environ.get("PHONE_CONFIDENCE_THRESHOLD", "0.55"))
    PHONE_CONFIRMATION_FRAMES = int(os.environ.get("PHONE_CONFIRMATION_FRAMES", "3"))
    PHONE_EVENT_COOLDOWN = float(os.environ.get("PHONE_EVENT_COOLDOWN", "30"))
    PHONE_EVIDENCE_FOLDER = os.path.join(BASE_DIR, "uploads", "evidence")

    FACE_ABSENCE_THRESHOLD_SECONDS = float(os.environ.get("FACE_ABSENCE_THRESHOLD_SECONDS", "2"))
    FACE_ABSENCE_TERMINATION_SECONDS = float(os.environ.get("FACE_ABSENCE_TERMINATION_SECONDS", "10"))

    HOST = os.environ.get("EXAMGUARD_HOST", "127.0.0.1")
    PORT = int(os.environ.get("EXAMGUARD_PORT", "5000"))
    DEBUG = os.environ.get("EXAMGUARD_DEBUG", "0").lower() in ("1", "true", "yes")