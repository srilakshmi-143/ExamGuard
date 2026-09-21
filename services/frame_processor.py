import base64
import cv2
import numpy as np

class FrameProcessor:
    @staticmethod
    def decode_base64_image(base64_string):
        """Decodes raw base64 camera image string into OpenCV numpy image buffer."""
        if not base64_string:
            return None
        try:
            if ',' in base64_string:
                header, encoded = base64_string.split(',', 1)
            else:
                encoded = base64_string
            image_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"[FrameProcessor Error] Failed to decode image: {e}")
            return None