import logging
import threading
import time
import numpy as np
import cv2
from .model_loader import ModelLoader

logger = logging.getLogger(__name__)

class FaceRecognizer:
    def __init__(self, app=None, threshold=0.6):
        self.app = app
        self.threshold = threshold
        self._lock = threading.RLock()
        
        # known_faces: user_id -> { "name": name, "feature": np.ndarray }
        self.known_faces = {}
        self._last_reload_time = 0.0
        self._refresh_interval = 30.0  # 30 seconds reload interval

    def reload_known_faces(self):
        """Reload all registered faces from the SQLite database."""
        if self.app is None:
            logger.warning("No Flask app instance provided, skipping face cache reload.")
            return

        logger.info("Reloading known faces from database...")
        try:
            # We import RegisteredFace inside the method to avoid circular imports
            with self.app.app_context():
                from models.face import RegisteredFace
                faces = RegisteredFace.query.all()
                
                new_faces = {}
                for face in faces:
                    if not face.feature_blob:
                        continue
                    try:
                        # Convert blob back to float32 numpy array
                        feature_arr = np.frombuffer(face.feature_blob, dtype=np.float32)
                        # MobileFaceNet usually produces 128-dimensional features
                        if len(feature_arr) > 0:
                            # Normalize just in case
                            feature_arr = feature_arr / (np.linalg.norm(feature_arr) + 1e-6)
                            new_faces[face.id] = {
                                "name": face.name,
                                "feature": feature_arr
                            }
                    except Exception as fe:
                        logger.error(f"Error parsing face feature for user ID {face.id}: {fe}")
                
                with self._lock:
                    self.known_faces = new_faces
                    self._last_reload_time = time.time()
                logger.info(f"Successfully loaded {len(self.known_faces)} face encodings into cache.")
                
        except Exception as e:
            logger.error(f"Error reloading known faces from database: {e}")

    def _auto_reload_if_needed(self):
        """Automatically trigger reload if refresh interval has expired."""
        if time.time() - self._last_reload_time > self._refresh_interval:
            self.reload_known_faces()

    def extract_feature(self, face_crop):
        """Extract a 128-dimensional L2-normalized feature vector from a face crop."""
        if face_crop is None or face_crop.size == 0:
            return None

        try:
            # 1. Preprocess crop for MobileFaceNet
            # MobileFaceNet input is 112x112 RGB
            blob = cv2.dnn.blobFromImage(
                face_crop,
                scalefactor=1.0/128.0,
                size=(112, 112),
                mean=(127.5, 127.5, 127.5),
                swapRB=True
            )
            
            # 2. Forward pass
            net = ModelLoader.get_face_recognizer()
            net.setInput(blob)
            feature = net.forward()
            
            # 3. Postprocess feature (flatten & normalize)
            feature = feature.flatten()
            norm = np.linalg.norm(feature)
            if norm > 0:
                feature = feature / norm
            return feature
            
        except Exception as e:
            logger.error(f"Error extracting face feature: {e}")
            return None

    def detect_and_recognize_in_person(self, frame, person_box):
        """
        Detect and recognize a face within a detected person bounding box.
        person_box is [x1, y1, x2, y2] absolute coordinates.
        Returns: face_found (bool), face_box_norm (list or None), name (str), user_id (int or None), distance (float)
        """
        x1, y1, x2, y2 = person_box
        fh, fw = frame.shape[:2]
        
        # Ensure box is within frame bounds
        x1 = max(0, min(fw - 1, x1))
        y1 = max(0, min(fh - 1, y1))
        x2 = max(0, min(fw - 1, x2))
        y2 = max(0, min(fh - 1, y2))
        
        if x2 <= x1 or y2 <= y1:
            return False, None, "Stranger", None, 1.0

        person_crop = frame[y1:y2, x1:x2]
        ch, cw = person_crop.shape[:2]
        if ch < 20 or cw < 20: # too small
            return False, None, "Stranger", None, 1.0

        try:
            detector = ModelLoader.get_face_detector()
            # Set input size for YuNet based on cropped region
            detector.setInputSize((cw, ch))
            
            retval, faces = detector.detect(person_crop)
            if faces is None or len(faces) == 0:
                return False, None, "Stranger", None, 1.0

            # Get the face with the highest confidence
            # face elements: [x, y, w, h, x_re, y_re, ...]
            best_face = faces[0]
            if not np.isfinite(best_face[0:4]).all():
                return False, None, "Stranger", None, 1.0
            fx, fy, f_w, f_h = map(int, best_face[0:4])
            
            # Add a small padding to face crop (about 15%)
            pad_w = int(f_w * 0.15)
            pad_h = int(f_h * 0.15)
            
            face_x1 = max(0, fx - pad_w)
            face_y1 = max(0, fy - pad_h)
            face_x2 = min(cw, fx + f_w + pad_w)
            face_y2 = min(ch, fy + f_h + pad_h)
            
            face_crop = person_crop[face_y1:face_y2, face_x1:face_x2]
            if face_crop.size == 0:
                return False, None, "Stranger", None, 1.0
                
            # Extract feature
            feat = self.extract_feature(face_crop)
            if feat is None:
                return False, None, "Stranger", None, 1.0

            # Match against known faces
            self._auto_reload_if_needed()
            
            best_match_id = None
            best_match_name = "Stranger"
            min_dist = 2.0  # L2 distance range is 0.0 to 2.0 for normalized vectors
            
            with self._lock:
                for user_id, info in self.known_faces.items():
                    known_feat = info["feature"]
                    dist = float(np.linalg.norm(feat - known_feat))
                    if dist < min_dist:
                        min_dist = dist
                        if dist <= self.threshold:
                            best_match_id = user_id
                            best_match_name = info["name"]

            # Calculate normalized face coordinates relative to the entire frame
            abs_face_x1 = x1 + fx
            abs_face_y1 = y1 + fy
            abs_face_x2 = x1 + fx + f_w
            abs_face_y2 = y1 + fy + f_h
            
            face_box_norm = [
                max(0.0, min(1.0, abs_face_x1 / fw)),
                max(0.0, min(1.0, abs_face_y1 / fh)),
                max(0.0, min(1.0, abs_face_x2 / fw)),
                max(0.0, min(1.0, abs_face_y2 / fh))
            ]
            
            return True, face_box_norm, best_match_name, best_match_id, min_dist

        except Exception as e:
            logger.error(f"Error in detect_and_recognize_in_person: {e}")
            return False, None, "Stranger", None, 1.0

    def compare(self, known_feature, candidate_feature):
        """Compare two features for backward compatibility."""
        distance = np.linalg.norm(np.asarray(known_feature) - np.asarray(candidate_feature))
        return {"matched": distance <= self.threshold, "distance": float(distance)}
