import cv2
import numpy as np
import logging
import time

logger = logging.getLogger(__name__)

class LivenessDetector:
    """
    Hybrid Liveness Detector combining:
    1. MiniFASNetV2 ONNX deep-learning model (Live probability)
    2. Laplacian variance (Clarity / focus analysis)
    3. HSV color distribution (Standard deviation check to filter flat screen/print playbacks)
    4. 3-frame anomalous shift debounce logic to prevent YOLO box jitter from resetting white-list.
    5. Stateful 3-second TTL white-list tracking.
    """
    def __init__(self, blur_threshold=80.0):
        self.blur_threshold = blur_threshold
        self.classifier = None
        
        # State tracking: { track_id: { "expire": timestamp, "consecutive_anomalies": int, "last_box": [x, y, w, h] } }
        self.live_cache = {}
        
        # Decision weights (w1 + w2 + w3 = 1.0)
        self.w1 = 0.6  # MiniFASNetV2 probability
        self.w2 = 0.2  # Laplacian variance (normalized clarity)
        self.w3 = 0.2  # HSV saturation and value variance (normalized)

    def _init_classifier(self):
        if self.classifier is None:
            from .model_loader import ModelLoader, WEIGHTS_DIR
            import os
            from .liveness_net import SilentFaceAntiSpoofing
            
            model_path = os.path.join(WEIGHTS_DIR, '2.7_80x80_MiniFASNetV2.onnx')
            self.classifier = SilentFaceAntiSpoofing(model_path)

    def check(self, track_id, frame, face_box):
        """
        Evaluate if a tracked person's face is live, spoof, or unknown.
        track_id: unique integer identifier for the tracked target
        frame: full input frame
        face_box: face bounding box in frame coordinates, format [x, y, w, h]
        
        Returns: 'Live', 'Spoof', or 'Unknown'
        """
        self._init_classifier()
        now = time.time()
        
        if track_id is not None:
            cached = self.live_cache.get(track_id)
            # Check if cache is valid and not expired
            if cached and now <= cached.get("expire", 0):
                # Run 3-frame anomaly check
                last_box = cached.get("last_box")
                if last_box:
                    lx, ly, lw, lh = last_box
                    x, y, w, h = face_box
                    
                    area = w * h
                    last_area = lw * lh
                    area_ratio = area / last_area if last_area > 0 else 1.0
                    
                    cx, cy = x + w / 2.0, y + h / 2.0
                    lcx, lcy = lx + lw / 2.0, ly + lh / 2.0
                    center_dist = np.sqrt((cx - lcx)**2 + (cy - lcy)**2)
                    norm_dist = center_dist / max(lw, lh) if max(lw, lh) > 0 else 0.0
                    
                    is_anomalous = (area_ratio < 0.6 or area_ratio > 1.5 or norm_dist > 0.3)
                    
                    if is_anomalous:
                        cached["consecutive_anomalies"] += 1
                    else:
                        cached["consecutive_anomalies"] = 0
                        
                    # Update box reference
                    cached["last_box"] = face_box
                    
                    if cached["consecutive_anomalies"] >= 3:
                        logger.warning(f"Liveness tracking anomaly detected for ID {track_id} (consecutive: 3). Clearing cache.")
                        self.live_cache.pop(track_id, None)
                    else:
                        # Smooth over jitter, return Live using cached state
                        return 'Live'
        
        # Crop and verify liveness
        crop = self.classifier.crop(frame, face_box)
        if crop is None or crop.size == 0:
            return 'Unknown'
            
        # 1. MiniFASNetV2 inference
        from .model_loader import ModelLoader
        session = ModelLoader.get_liveness_net()
        probs = self.classifier.predict(session, crop)
        P_fas = float(probs[0][1])  # Class 1 is Real
        
        # 2. Laplacian Variance (clarity)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        Var_lap_norm = min(1.0, laplacian_var / 300.0)
        
        # 3. HSV saturation/value variance (reflections and flat color distributions)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        h_chan, s_chan, v_chan = cv2.split(hsv)
        std_s = float(np.std(s_chan))
        std_v = float(np.std(v_chan))
        std_s_norm = min(1.0, std_s / 20.0)
        std_v_norm = min(1.0, std_v / 30.0)
        Std_hsv_norm = 0.5 * std_s_norm + 0.5 * std_v_norm
        
        # 4. Box motion penalty
        Penalty_box = 0.0
        if track_id is not None:
            prev_entry = self.live_cache.get(track_id)
            if prev_entry and prev_entry.get("last_box"):
                lx, ly, lw, lh = prev_entry["last_box"]
                x, y, w, h = face_box
                area_ratio = (w * h) / (lw * lh) if (lw * lh) > 0 else 1.0
                cx, cy = x + w / 2.0, y + h / 2.0
                lcx, lcy = lx + lw / 2.0, ly + lh / 2.0
                norm_dist = np.sqrt((cx - lcx)**2 + (cy - lcy)**2) / max(lw, lh) if max(lw, lh) > 0 else 0.0
                
                # Single frame jump penalty
                if area_ratio < 0.8 or area_ratio > 1.25 or norm_dist > 0.15:
                    Penalty_box = 0.2
        
        # 5. Hybrid decision fusion
        Score = self.w1 * P_fas + self.w2 * Var_lap_norm + self.w3 * Std_hsv_norm - Penalty_box
        Score = max(0.0, min(1.0, Score))
        
        logger.debug(f"Liveness ID {track_id}: Score: {Score:.2f} (P_fas: {P_fas:.2f}, Laplacian: {laplacian_var:.1f}, HSV: {std_s:.1f}/{std_v:.1f}, Penalty: {Penalty_box:.1f})")
        
        if Score >= 0.65:
            if track_id is not None:
                self.live_cache[track_id] = {
                    "expire": now + 3.0,
                    "consecutive_anomalies": 0,
                    "last_box": face_box
                }
            return 'Live'
        elif Score <= 0.35:
            return 'Spoof'
        else:
            # Intermediate state, request next frame
            if track_id is not None and track_id not in self.live_cache:
                # Track box position for future frames even if not verified yet
                self.live_cache[track_id] = {
                    "expire": 0.0,
                    "consecutive_anomalies": 0,
                    "last_box": face_box
                }
            return 'Unknown'

    def is_live(self, face_crop) -> tuple[bool, float]:
        """
        Evaluate if a raw face crop is live or a spoofing attempt.
        Maintains backward compatibility.
        """
        if face_crop is None or face_crop.size == 0:
            return False, 0.0
            
        try:
            self._init_classifier()
            
            # MiniFASNetV2 inference (Resize first)
            from .model_loader import ModelLoader
            session = ModelLoader.get_liveness_net()
            resized = cv2.resize(face_crop, self.classifier.input_size)
            probs = self.classifier.predict(session, resized)
            P_fas = float(probs[0][1])
            
            # Heuristics
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            Var_lap_norm = min(1.0, laplacian_var / 300.0)
            
            hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            std_s = float(np.std(s))
            std_v = float(np.std(v))
            std_s_norm = min(1.0, std_s / 20.0)
            std_v_norm = min(1.0, std_v / 30.0)
            Std_hsv_norm = 0.5 * std_s_norm + 0.5 * std_v_norm
            
            Score = self.w1 * P_fas + self.w2 * Var_lap_norm + self.w3 * Std_hsv_norm
            Score = max(0.0, min(1.0, Score))
            
            # Threshold is 0.5 for binary classification
            return Score >= 0.5, Score
            
        except Exception as e:
            logger.error(f"Error in legacy is_live method: {e}")
            return True, 1.0
