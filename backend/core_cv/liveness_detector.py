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
    4. Moire pattern detection (FFT-based frequency analysis for phone screens)
    5. Reflection detection (Highlight regions for screen glare)
    6. 3-frame anomalous shift debounce logic to prevent YOLO box jitter from resetting white-list.
    7. Stateful 3-second TTL white-list tracking.
    
    Optimized for phone screen spoof detection.
    """
    def __init__(self, blur_threshold=80.0):
        self.blur_threshold = blur_threshold
        self.classifier = None
        
        # State tracking: { track_id: { "expire": timestamp, "consecutive_anomalies": int, "last_box": [x, y, w, h] } }
        self.live_cache = {}
        
        # Decision weights (optimized for phone screen detection)
        self.w1 = 0.50  # MiniFASNetV2 probability (reduced to allow heuristics more weight)
        self.w2 = 0.15  # Laplacian variance (normalized clarity)
        self.w3 = 0.15  # HSV saturation and value variance (normalized)
        self.w4 = 0.20  # Moire pattern score (phone screen specific)

    def _init_classifier(self):
        if self.classifier is None:
            from .model_loader import ModelLoader, WEIGHTS_DIR
            import os
            from .liveness_net import SilentFaceAntiSpoofing
            
            model_path = os.path.join(WEIGHTS_DIR, '2.7_80x80_MiniFASNetV2.onnx')
            self.classifier = SilentFaceAntiSpoofing(model_path)
    
    def _detect_moire_pattern(self, crop):
        """
        Detect Moire pattern using FFT frequency analysis.
        Phone screens exhibit characteristic high-frequency interference patterns.
        Returns: score in [0, 1] where higher = more likely phone screen
        """
        try:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            
            # Apply FFT
            f = np.fft.fft2(gray)
            fshift = np.fft.fftshift(f)
            magnitude_spectrum = np.abs(fshift)
            
            # Normalize
            magnitude_spectrum = np.log1p(magnitude_spectrum)
            magnitude_spectrum = (magnitude_spectrum - magnitude_spectrum.min()) / (magnitude_spectrum.max() - magnitude_spectrum.min() + 1e-6)
            
            # Analyze high-frequency components (Moire pattern indicator)
            h, w = magnitude_spectrum.shape
            center_y, center_x = h // 2, w // 2
            
            # Create frequency band masks
            inner_mask = np.zeros_like(magnitude_spectrum, dtype=bool)
            outer_mask = np.zeros_like(magnitude_spectrum, dtype=bool)
            
            inner_radius = min(h, w) // 8
            outer_radius = min(h, w) // 3
            
            y, x = np.ogrid[:h, :w]
            dist_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            
            inner_mask = dist_from_center < inner_radius
            outer_mask = (dist_from_center >= inner_radius) & (dist_from_center < outer_radius)
            
            # Calculate energy in different frequency bands
            low_freq_energy = np.mean(magnitude_spectrum[inner_mask])
            mid_freq_energy = np.mean(magnitude_spectrum[outer_mask])
            
            # Moire pattern: high mid-frequency energy relative to low-frequency
            if low_freq_energy > 0:
                freq_ratio = mid_freq_energy / low_freq_energy
            else:
                freq_ratio = 0
            
            # Also check for periodic patterns (another Moire indicator)
            # Calculate variance of magnitude spectrum
            freq_variance = np.var(magnitude_spectrum)
            
            # Combine indicators
            moire_score = min(1.0, freq_ratio * 2.0 + freq_variance * 3.0)
            
            return moire_score
            
        except Exception as e:
            logger.debug(f"Moire detection error: {e}")
            return 0.0
    
    def _detect_reflection(self, crop):
        """
        Detect screen reflections and glare.
        Phone screens often have bright specular reflections.
        Returns: score in [0, 1] where higher = more likely screen
        """
        try:
            # Convert to HSV
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            v_chan = hsv[:, :, 2]
            
            # Count very bright pixels (potential reflections)
            bright_threshold = 220
            bright_ratio = np.sum(v_chan > bright_threshold) / v_chan.size
            
            # Check for localized bright spots (specular reflection)
            if bright_ratio > 0.05:
                # Find bright regions
                bright_mask = v_chan > bright_threshold
                contours, _ = cv2.findContours(bright_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Calculate largest bright region
                    max_area = max(cv2.contourArea(c) for c in contours)
                    relative_area = max_area / v_chan.size
                    
                    # Screen reflections often form large, irregular bright regions
                    if relative_area > 0.02:
                        return min(1.0, relative_area * 10)
            
            return bright_ratio * 2
            
        except Exception as e:
            logger.debug(f"Reflection detection error: {e}")
            return 0.0

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
                        # Auto-extend TTL (max 30s)
                        remaining = cached["expire"] - now
                        if remaining < 25.0:
                            cached["expire"] = now + min(remaining + 3.0, 30.0)
                        
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
        
        # 2. P_fas hard gate: MiniFASNetV2 is the authority on spoof detection.
        #    High-quality printed photos / phone screens can have good Laplacian
        #    clarity and HSV color range, fooling the heuristic-only check.
        #    If the deep model is confident it's fake (P_fas <= 0.35), trust it.
        if P_fas <= 0.35:
            return 'Spoof'
        if P_fas >= 0.90:
            if track_id is not None:
                self.live_cache[track_id] = {
                    "expire": now + 8.0,
                    "consecutive_anomalies": 0,
                    "last_box": face_box
                }
            return 'Live'
        
        # 3. Laplacian Variance (clarity)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        Var_lap_norm = min(1.0, laplacian_var / 300.0)
        
        # 4. HSV saturation/value variance (reflections and flat color distributions)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        h_chan, s_chan, v_chan = cv2.split(hsv)
        std_s = float(np.std(s_chan))
        std_v = float(np.std(v_chan))
        std_s_norm = min(1.0, std_s / 20.0)
        std_v_norm = min(1.0, std_v / 30.0)
        Std_hsv_norm = 0.5 * std_s_norm + 0.5 * std_v_norm
        
        # 5. Moire pattern detection (phone screen specific)
        Moire_score = self._detect_moire_pattern(crop)
        
        # 6. Reflection detection (screen glare)
        Reflection_score = self._detect_reflection(crop)
        
        # Phone screen penalty: combine Moire and reflection
        Phone_penalty = 0.0
        if Moire_score > 0.3 or Reflection_score > 0.2:
            Phone_penalty = max(Moire_score, Reflection_score) * 0.7
        
        # 7. Box motion penalty
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
                if area_ratio < 0.6 or area_ratio > 1.6 or norm_dist > 0.25:
                    Penalty_box = 0.1
        
        # 8. Hybrid decision fusion (optimized for phone screen detection)
        #    Lower score = more likely spoof
        Score = self.w1 * P_fas + self.w2 * Var_lap_norm + self.w3 * Std_hsv_norm - Penalty_box - Phone_penalty
        Score = max(0.0, min(1.0, Score))
        
        logger.debug(f"Liveness ID {track_id}: Score: {Score:.2f} (P_fas: {P_fas:.2f}, Laplacian: {laplacian_var:.1f}, HSV: {std_s:.1f}/{std_v:.1f}, Moire: {Moire_score:.2f}, Reflection: {Reflection_score:.2f}, Penalty: {Penalty_box:.1f})")
        
        # 9. Final decision (adjusted thresholds for better phone screen detection)
        if Score >= 0.40:
            if track_id is not None:
                self.live_cache[track_id] = {
                    "expire": now + 8.0,
                    "consecutive_anomalies": 0,
                    "last_box": face_box
                }
            return 'Live'
        elif Score <= 0.30:
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
