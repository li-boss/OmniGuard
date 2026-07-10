import logging
import threading
import time
import numpy as np
import cv2
from .model_loader import ModelLoader

logger = logging.getLogger(__name__)

# Helper functions for face alignment and similarity calculation
REFERENCE_FACIAL_POINTS = np.array([
    [30.2946, 51.6963],  # Left Eye
    [65.5318, 51.5014],  # Right Eye
    [48.0252, 71.7366],  # Nose Tip
    [33.5493, 92.3655],  # Left Mouth Corner
    [62.7299, 92.2041]   # Right Mouth Corner
], dtype=np.float32)

def align_face(face_img, landmarks_5point):
    """
    Perform 5-point similarity transformation to align and crop face to 112x112.
    """
    try:
        tfm, _ = cv2.estimateAffinePartial2D(landmarks_5point, REFERENCE_FACIAL_POINTS)
        if tfm is None:
            return cv2.resize(face_img, (112, 112))
        aligned_face = cv2.warpAffine(face_img, tfm, (112, 112))
        return aligned_face
    except Exception:
        return cv2.resize(face_img, (112, 112))

def calc_similarity(feat1, feat2):
    """Calculate the cosine similarity between two L2-normalized feature vectors."""
    return float(np.dot(feat1, feat2))


class FaceRecognizer:
    def __init__(self, app=None, threshold=None):
        self.app = app
        if threshold is not None:
            self.threshold = threshold
        elif app is not None:
            self.threshold = app.config.get("FACE_MATCH_THRESHOLD", 0.5)
        else:
            try:
                from config import Config
                self.threshold = getattr(Config, "FACE_MATCH_THRESHOLD", 0.5)
            except Exception:
                self.threshold = 0.5
        
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
                        # Normalize just in case
                        if len(feature_arr) > 0:
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
        """Extract a 512-dimensional L2-normalized feature vector from an aligned face crop."""
        if face_crop is None or face_crop.size == 0:
            return None

        try:
            # Always ensure the input face crop is resized to 112x112
            if face_crop.shape[0] != 112 or face_crop.shape[1] != 112:
                face_crop = cv2.resize(face_crop, (112, 112))

            # 1. Preprocess crop for ArcFace
            # Input image face_crop is 112x112 BGR.
            # Normalization: (x / 255.0 - 0.5) / 0.5 -> [-1, 1]
            img = face_crop.astype(np.float32)
            img = (img / 255.0 - 0.5) / 0.5
            
            # Convert HWC to CHW
            img = np.transpose(img, (2, 0, 1))
            img = np.expand_dims(img, axis=0) # Add batch dimension -> (1, 3, 112, 112)

            # 2. Forward pass via ThreadSafeONNXSession
            net = ModelLoader.get_face_recognizer()
            input_name = net.session.get_inputs()[0].name
            output_name = net.session.get_outputs()[0].name
            
            outputs = net.run([output_name], {input_name: img})
            feature = outputs[0].flatten()

            # 3. Postprocess feature (L2 Normalize)
            norm = np.linalg.norm(feature)
            if norm > 0:
                feature = feature / norm
            return feature

        except Exception as e:
            logger.error(f"Error extracting face feature: {e}")
            return None

    def detect_and_recognize_in_person(self, frame, person_box):
        """
        Detect and recognize a face within a detected person bounding box using YuNet and ArcFace.
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
            detector.setInputSize((cw, ch))
            
            retval, faces = detector.detect(person_crop)
            if faces is None or len(faces) == 0:
                return False, None, "Stranger", None, 1.0

            # Get the face with the highest confidence
            best_face = faces[0]
            if not np.isfinite(best_face[0:4]).all():
                return False, None, "Stranger", None, 1.0
            fx, fy, f_w, f_h = map(int, best_face[0:4])
            
            # Extract 5 landmarks coordinates relative to person_crop
            landmarks = np.array([
                [best_face[4], best_face[5]],   # Left eye
                [best_face[6], best_face[7]],   # Right eye
                [best_face[8], best_face[9]],   # Nose tip
                [best_face[10], best_face[11]], # Left mouth corner
                [best_face[12], best_face[13]]  # Right mouth corner
            ], dtype=np.float32)

            # 1. Padded crop for liveness detection
            pad_w = int(f_w * 0.15)
            pad_h = int(f_h * 0.15)
            face_x1 = max(0, fx - pad_w)
            face_y1 = max(0, fy - pad_h)
            face_x2 = min(cw, fx + f_w + pad_w)
            face_y2 = min(ch, fy + f_h + pad_h)
            liveness_crop = person_crop[face_y1:face_y2, face_x1:face_x2]
            
            # Run liveness detection check
            if liveness_crop.size > 0:
                try:
                    from .liveness_detector import LivenessDetector
                    liveness_det = LivenessDetector()
                    is_live, live_conf = liveness_det.is_live(liveness_crop)
                    if not is_live:
                        logger.debug(f"Liveness spoof attack detected (confidence: {live_conf:.2f}). Treating as Stranger.")
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
                        return True, face_box_norm, "Stranger", None, 1.0
                except Exception as le:
                    logger.error(f"Error in liveness detection: {le}")

            # 2. Align face image for feature extraction
            aligned_face = align_face(person_crop, landmarks)
            
            # Extract feature (512-dimensional for ArcFace)
            feat = self.extract_feature(aligned_face)
            if feat is None:
                return False, None, "Stranger", None, 1.0

            # Match against known faces
            self._auto_reload_if_needed()
            
            best_match_id = None
            best_match_name = "Stranger"
            min_dist = 2.0
            
            is_arcface = (len(feat) == 512)
            max_sim = -1.0
            
            with self._lock:
                for user_id, info in self.known_faces.items():
                    known_feat = info["feature"]
                    if len(known_feat) != len(feat):
                        continue
                    
                    dist = float(np.linalg.norm(feat - known_feat))
                    if dist < min_dist:
                        min_dist = dist
                    
                    if is_arcface:
                        sim = calc_similarity(feat, known_feat)
                        if sim >= self.threshold:
                            if best_match_id is None or sim > max_sim:
                                max_sim = sim
                                best_match_id = user_id
                                best_match_name = info["name"]
                    else:
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
        feat1 = np.asarray(known_feature, dtype=np.float32)
        feat2 = np.asarray(candidate_feature, dtype=np.float32)
        
        norm1 = np.linalg.norm(feat1)
        if norm1 > 0:
            feat1 = feat1 / norm1
        norm2 = np.linalg.norm(feat2)
        if norm2 > 0:
            feat2 = feat2 / norm2

        distance = float(np.linalg.norm(feat1 - feat2))
        
        is_arcface = (len(feat1) == 512)
        if is_arcface:
            sim = calc_similarity(feat1, feat2)
            matched = (sim >= self.threshold)
        else:
            matched = (distance <= self.threshold)
            
        return {"matched": matched, "distance": distance}
