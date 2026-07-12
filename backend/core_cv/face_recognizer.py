import logging
import threading
import time
import numpy as np
import cv2
from .model_loader import ModelLoader

logger = logging.getLogger(__name__)

# Helper functions for face alignment and similarity calculation
REFERENCE_FACIAL_POINTS = np.array([
    [38.2946, 51.6963],   # Left Eye
    [73.5318, 51.5014],   # Right Eye
    [56.0252, 71.7366],   # Nose Tip
    [41.5493, 92.3655],   # Left Mouth Corner
    [70.7299, 92.2041]    # Right Mouth Corner
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

def is_good_face(face_img, min_blur_threshold=20.0, min_brightness=40, max_brightness=230):
    """
    Filter face crops that are too blurry or have poor lighting (too dark/too bright).
    """
    if face_img is None or face_img.size == 0:
        return False
    try:
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < min_blur_threshold:
            logger.debug(f"Face quality rejected: Laplacian variance {laplacian_var:.1f} < threshold {min_blur_threshold}")
            return False
        mean_brightness = np.mean(gray)
        if mean_brightness < min_brightness or mean_brightness > max_brightness:
            logger.debug(f"Face quality rejected: Mean brightness {mean_brightness:.1f} out of range")
            return False
        return True
    except Exception as e:
        logger.warning(f"Error during face quality checking: {e}")
        return False

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
        self.liveness_detector = None

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

    def detect_and_recognize_in_person(self, frame, person_box, track_id=None):
        """
        Detect and recognize a face within a detected person bounding box using RetinaFace and ArcFace.
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
            # Pad crop to square to preserve aspect ratio for RetinaFace detector
            square_size = max(ch, cw)
            pad_x = 0
            pad_y = 0
            if ch > cw:
                pad_x = (ch - cw) // 2
                person_crop_square = cv2.copyMakeBorder(person_crop, 0, 0, pad_x, ch - cw - pad_x, cv2.BORDER_CONSTANT, value=[0, 0, 0])
            else:
                pad_y = (cw - ch) // 2
                person_crop_square = cv2.copyMakeBorder(person_crop, pad_y, cw - ch - pad_y, 0, 0, cv2.BORDER_CONSTANT, value=[0, 0, 0])

            # Resize square crop to (256, 256)
            person_crop_resized = cv2.resize(person_crop_square, (256, 256))
            detector = ModelLoader.get_face_detector()
            
            resp = detector.inference(person_crop_resized)
            faces = resp.get("bbox", [])
            landmarks_all = resp.get("landmarks", [])
            
            if faces is None or len(faces) == 0:
                return False, None, "Stranger", None, 1.0

            # Get the face with the highest score
            best_face = faces[0]
            fx1, fy1, fx2, fy2, score = best_face
            
            # Scale coordinates back to square crop size
            scale_x = square_size / 256.0
            scale_y = square_size / 256.0
            
            # Map back to original person_crop coordinates by subtracting the pads
            fx = int(fx1 * scale_x - pad_x)
            fy = int(fy1 * scale_y - pad_y)
            f_w = int((fx2 - fx1) * scale_x)
            f_h = int((fy2 - fy1) * scale_y)
            
            # Map landmarks back to person_crop coordinate space
            landmarks = landmarks_all[0].copy().astype(np.float32)
            landmarks[:, 0] = landmarks[:, 0] * scale_x - pad_x
            landmarks[:, 1] = landmarks[:, 1] * scale_y - pad_y

            # Calculate absolute face coordinates in frame coordinate space
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

            # Lazy-load the liveness detector
            if self.liveness_detector is None:
                from .liveness_detector import LivenessDetector
                self.liveness_detector = LivenessDetector()

            # Run stateful hybrid liveness check
            liveness_status = self.liveness_detector.check(track_id, frame, [abs_face_x1, abs_face_y1, f_w, f_h])
            
            if liveness_status == 'Unknown':
                logger.debug(f"Liveness status 'Unknown' for track ID {track_id}. Requesting next frame.")
                return True, face_box_norm, "Analyzing...", None, 1.0
            elif liveness_status == 'Spoof':
                logger.warning(f"Liveness spoof attack detected for track ID {track_id}. Blocking.")
                return True, face_box_norm, "Spoof/Attack", None, 1.0

            # 2. Align face image for feature extraction
            aligned_face = align_face(person_crop, landmarks)
            
            # Quality check: Blur and brightness filtering
            if not is_good_face(aligned_face, min_blur_threshold=5.0):
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
