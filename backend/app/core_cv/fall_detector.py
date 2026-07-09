import time


try:
    import cv2
except ImportError:  # pragma: no cover - optional runtime dependency
    cv2 = None


class FallDetector:
    def __init__(
        self,
        aspect_ratio_threshold=1.25,
        floor_ratio_threshold=0.52,
        min_confidence=0.58,
        confirm_frames=2,
        use_hog=True,
    ):
        self.aspect_ratio_threshold = aspect_ratio_threshold
        self.floor_ratio_threshold = floor_ratio_threshold
        self.min_confidence = min_confidence
        self.confirm_frames = max(1, int(confirm_frames))
        self.use_hog = use_hog
        self.hog = None
        self.tracks = {}
        self.next_track_id = 1

        if cv2 is not None and use_hog:
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect_frame(self, frame, detections=None):
        people = self._person_candidates(frame, detections)
        confirmed = []
        now = time.time()

        for person in people:
            score, reason = self._fall_score(person["box"], frame)
            if score < self.min_confidence:
                continue

            track = self._track(person["box"], now)
            track["fall_frames"] += 1
            if track["fall_frames"] < self.confirm_frames:
                continue

            confirmed.append({
                "eventType": "fall",
                "type": "fall",
                "title": "疑似摔倒",
                "severity": "high",
                "confidence": round(float(score), 3),
                "box": person["box"],
                "box_norm": self._normalize_box(person["box"], frame),
                "source": person["source"],
                "reason": reason,
                "detectedAt": now,
            })

        self._cleanup_tracks(now)
        return confirmed

    def _person_candidates(self, frame, detections=None):
        candidates = []
        for detection in detections or []:
            box = self._box_from_detection(detection, frame)
            if box is None:
                continue
            if self._is_explicit_fall(detection):
                candidates.append({"box": box, "source": "detection:fall"})
                continue
            if self._is_person(detection):
                candidates.append({"box": box, "source": "detection:person"})

        if candidates or not self.use_hog or self.hog is None or frame is None:
            return candidates
        return self._hog_people(frame)

    def _hog_people(self, frame):
        height, width = frame.shape[:2]
        scale = 1.0
        resized = frame
        max_side = max(height, width)
        if max_side > 720:
            scale = 720.0 / max_side
            resized = cv2.resize(frame, (int(width * scale), int(height * scale)))

        boxes, weights = self.hog.detectMultiScale(
            resized,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
        )
        if len(boxes) == 0:
            return []

        nms_boxes = []
        confidences = []
        for (x, y, box_width, box_height), weight in zip(boxes, weights):
            nms_boxes.append([int(x), int(y), int(box_width), int(box_height)])
            confidences.append(float(weight))
        indices = cv2.dnn.NMSBoxes(nms_boxes, confidences, 0.2, 0.35)
        if len(indices) == 0:
            return []

        candidates = []
        for raw_idx in indices:
            if isinstance(raw_idx, (list, tuple)) or hasattr(raw_idx, "__len__"):
                idx = int(raw_idx[0])
            else:
                idx = int(raw_idx)
            x, y, box_width, box_height = nms_boxes[idx]
            if scale != 1.0:
                x = int(x / scale)
                y = int(y / scale)
                box_width = int(box_width / scale)
                box_height = int(box_height / scale)
            candidates.append({
                "box": [x, y, x + box_width, y + box_height],
                "source": "hog:person",
            })
        return candidates

    def _fall_score(self, box, frame):
        x1, y1, x2, y2 = box
        width = max(1.0, float(x2 - x1))
        height = max(1.0, float(y2 - y1))
        frame_height = float(frame.shape[0]) if frame is not None and hasattr(frame, "shape") else max(y2, 1)
        aspect_ratio = width / height
        bottom_ratio = y2 / max(frame_height, 1.0)

        aspect_score = min(1.0, max(0.0, (aspect_ratio - 0.95) / (self.aspect_ratio_threshold - 0.95)))
        floor_score = min(1.0, max(0.0, (bottom_ratio - 0.35) / (self.floor_ratio_threshold - 0.35)))
        score = 0.68 * aspect_score + 0.32 * floor_score
        reason = f"aspect={aspect_ratio:.2f}, bottom={bottom_ratio:.2f}"
        return score, reason

    def _track(self, box, now):
        best_id = None
        best_score = 0.0
        for track_id, track in self.tracks.items():
            score = self._iou(track["box"], box)
            if score > best_score:
                best_id = track_id
                best_score = score

        if best_id is None or best_score < 0.25:
            best_id = self.next_track_id
            self.next_track_id += 1
            self.tracks[best_id] = {"box": box, "fall_frames": 0, "last_seen": now}
        else:
            self.tracks[best_id]["box"] = box
            self.tracks[best_id]["last_seen"] = now
        return self.tracks[best_id]

    def _cleanup_tracks(self, now, timeout_seconds=3.0):
        for track_id, track in list(self.tracks.items()):
            if now - track["last_seen"] > timeout_seconds:
                self.tracks.pop(track_id, None)

    def _box_from_detection(self, detection, frame=None):
        box = detection.get("box") or detection.get("box_norm")
        if box and len(box) == 4:
            return self._to_pixel_box(box, frame)

        bbox = detection.get("bbox")
        if bbox and len(bbox) == 4:
            x, y, width, height = bbox
            return self._to_pixel_box([x, y, x + width, y + height], frame)
        return None

    def _to_pixel_box(self, box, frame=None):
        values = [float(value) for value in box]
        if frame is not None and hasattr(frame, "shape") and max(values) <= 1.0:
            height, width = frame.shape[:2]
            values = [values[0] * width, values[1] * height, values[2] * width, values[3] * height]
        return [int(round(value)) for value in values]

    def _is_person(self, detection):
        label = str(
            detection.get("class")
            or detection.get("className")
            or detection.get("label")
            or detection.get("name")
            or detection.get("category")
            or ""
        ).lower()
        return label in {"person", "people", "human", "pedestrian", "人体", "行人"}

    def _is_explicit_fall(self, detection):
        label = str(
            detection.get("eventType")
            or detection.get("event_type")
            or detection.get("type")
            or detection.get("label")
            or ""
        ).lower()
        return label in {"fall", "fallen", "fall_down", "摔倒", "跌倒"}

    def _normalize_box(self, box, frame):
        if frame is None or not hasattr(frame, "shape"):
            return box
        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            return box
        x1, y1, x2, y2 = box
        return [
            round(x1 / width, 4),
            round(y1 / height, 4),
            round(x2 / width, 4),
            round(y2 / height, 4),
        ]

    def _iou(self, left, right):
        xi1 = max(left[0], right[0])
        yi1 = max(left[1], right[1])
        xi2 = min(left[2], right[2])
        yi2 = min(left[3], right[3])
        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
        right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
        union_area = left_area + right_area - inter_area
        return 0.0 if union_area <= 0 else inter_area / union_area
