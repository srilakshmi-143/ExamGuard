import os
import cv2
import numpy as np
from config import Config

class FaceDetector:
    """
    Dedicated Face Detection Service using OpenCV Haar Cascades.
    Technically Honest: Used purely for localizing faces and counting present individuals.
    Does NOT perform facial recognition or identity matching.
    """
    def __init__(self):
        cascade_path = Config.HAAR_CASCADE_PATH
        if not os.path.exists(cascade_path):
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def detect_faces(self, frame):
        """
        Processes a BGR frame byte or array and detects human faces.
        Returns: status (str), bounding_boxes (list), face_count (int)
        """
        if frame is None or frame.size == 0:
            return "NO_FACE", [], 0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Detect faces with tuned parameters for examination lighting
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        face_count = len(faces)
        bounding_boxes = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for (x, y, w, h) in faces]

        if face_count == 0:
            status = "NO_FACE"
        elif face_count == 1:
            status = "SINGLE_FACE"
        else:
            status = "MULTIPLE_FACES"

        return status, bounding_boxes, face_count