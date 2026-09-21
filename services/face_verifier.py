import os
from typing import Any, Tuple, cast
import cv2  # type: ignore
import numpy as np

# Suppress linter warnings for dynamically imported face engines
try:
    import face_recognition  # type: ignore
    HAS_FACE_REC = True
except ImportError:
    HAS_FACE_REC = False

try:
    from deepface import DeepFace  # type: ignore
    HAS_DEEPFACE = True
except ImportError:
    HAS_DEEPFACE = False


class FaceVerifier:
    def __init__(self, tolerance: float = 0.65, lbph_threshold: float = 85.0) -> None:
        self.tolerance: float = tolerance
        self.lbph_threshold: float = lbph_threshold

    def verify(
        self, registered_photo_path: str, live_frame: Any
    ) -> Tuple[bool, float, str]:
        """Compares registered profile photo with live webcam frame.

        Returns: (verified, confidence, message)
        """
        if not registered_photo_path or not os.path.exists(registered_photo_path):
            return False, 0.0, f"Registered photo not found at path: {registered_photo_path}"

        if live_frame is None or not hasattr(live_frame, "size") or live_frame.size == 0:
            return False, 0.0, "Invalid or empty live webcam frame received."

        # Convert OpenCV BGR to RGB safely casted for static checkers
        frame_array = cast(np.ndarray, live_frame)
        if frame_array.ndim == 2:
            frame_array = cv2.cvtColor(frame_array, cv2.COLOR_GRAY2BGR)
        elif frame_array.ndim != 3 or frame_array.shape[2] != 3:
            return False, 0.0, "Unsupported webcam image format received."
        rgb_live_frame = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)

        # ----------------------------------------------------
        # OPTION A: Using face_recognition
        # ----------------------------------------------------
        if HAS_FACE_REC:
            try:
                registered_image = face_recognition.load_image_file(registered_photo_path)
                reg_encodings = face_recognition.face_encodings(registered_image)

                if not reg_encodings:
                    return False, 0.0, "No face detected in registered profile photo."

                live_encodings = face_recognition.face_encodings(rgb_live_frame)
                if not live_encodings:
                    return (
                        False,
                        0.0,
                        "No face detected in live camera. Ensure your face is clearly visible.",
                    )

                face_distance: float = float(
                    face_recognition.face_distance([reg_encodings[0]], live_encodings[0])[0]
                )
                confidence: float = round(max(0.0, (1.0 - face_distance)) * 100, 2)
                is_match: bool = bool(face_distance <= self.tolerance)

                if is_match:
                    return True, confidence, f"Identity verified successfully. ({confidence}% match)"
                return (
                    False,
                    confidence,
                    f"Face mismatch. Match confidence ({confidence}%) is below required threshold.",
                )

            except Exception as e:
                print(f"face_recognition error: {str(e)}")

        # ----------------------------------------------------
        # OPTION B: Using DeepFace
        # ----------------------------------------------------
        if HAS_DEEPFACE:
            try:
                result: Any = DeepFace.verify(
                    img1_path=registered_photo_path,
                    img2_path=rgb_live_frame,
                    enforce_detection=False,
                    distance_metric="cosine",
                )

                verified: bool = bool(result.get("verified", False))
                distance: float = float(result.get("distance", 1.0))
                confidence_df: float = round((1.0 - min(distance, 1.0)) * 100, 2)

                if verified:
                    return True, confidence_df, "Identity verified successfully."
                return (
                    False,
                    confidence_df,
                    "Face verification failed. Please adjust your position and try again.",
                )

            except Exception as e:
                print(f"DeepFace error: {str(e)}")

        # ----------------------------------------------------
        # OPTION C: OpenCV LBPH fallback
        # ----------------------------------------------------
        # Haar only locates faces. LBPH compares the registered and live
        # face crops when the optional embedding backends are unavailable.
        cascade_path: str = str(cv2.data.haarcascades) + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        registered_image = cv2.imread(registered_photo_path)
        if registered_image is None:
            return False, 0.0, "Registered photo could not be decoded."

        registered_gray = cv2.cvtColor(registered_image, cv2.COLOR_BGR2GRAY)
        live_gray = cv2.cvtColor(frame_array, cv2.COLOR_BGR2GRAY)
        registered_faces = face_cascade.detectMultiScale(
            registered_gray, 1.1, 5, minSize=(60, 60)
        )
        live_faces = face_cascade.detectMultiScale(
            live_gray, 1.1, 5, minSize=(60, 60)
        )

        if len(registered_faces) == 0:
            return False, 0.0, "No face detected in registered profile photo."
        if len(live_faces) == 0:
            return False, 0.0, "No face detected in live webcam stream."
        if len(live_faces) > 1:
            return False, 0.0, "Multiple faces detected in live webcam stream."
        if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            return False, 0.0, (
                "Identity verification is unavailable. Install face_recognition, "
                "DeepFace, or OpenCV contrib."
            )

        def crop_face(gray_image, face_box):
            x, y, width, height = face_box
            return cv2.resize(gray_image[y:y + height, x:x + width], (200, 200))

        registered_face = max(registered_faces, key=lambda box: box[2] * box[3])
        live_face = live_faces[0]
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train([crop_face(registered_gray, registered_face)], np.array([1]))
        _, distance = recognizer.predict(crop_face(live_gray, live_face))
        confidence = round(max(0.0, 100.0 * (1.0 - (distance / 150.0))), 2)

        if distance <= self.lbph_threshold:
            return True, confidence, f"Identity verified successfully. ({confidence}% match)"
        return False, confidence, f"Face mismatch. Match confidence ({confidence}%) is below required threshold."