import time
from collections import defaultdict


class RuleEngine:
    def __init__(self, alarm_cooldown_seconds=30):
        self.alarm_cooldown_seconds = alarm_cooldown_seconds
        self.entered_at = defaultdict(dict)

    def point_in_polygon(self, point, polygon):
        if isinstance(point, dict):
            x = point["x"]
            y = point["y"]
        else:
            x, y = point
        inside = False
        j = len(polygon) - 1
        for i, current in enumerate(polygon):
            previous = polygon[j]
            xi, yi = self._point_xy(current)
            xj, yj = self._point_xy(previous)
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def _point_xy(self, point):
        if isinstance(point, dict):
            return point["x"], point["y"]
        return point[0], point[1]

    def get_bottom_center(self, box_norm):
        x1, _y1, x2, y2 = box_norm
        return ((x1 + x2) / 2.0, y2)

    def evaluate_stay(self, object_id, box_norm, zone):
        zone_id = zone["id"]
        stay_seconds = zone.get("stay_seconds") or zone.get("staySeconds") or 5
        polygon = zone.get("polygon") or zone.get("points") or []
        point = self.get_bottom_center(box_norm)
        now = time.time()
        zone_state = self.entered_at[zone_id]

        if not self.point_in_polygon(point, polygon):
            zone_state.pop(object_id, None)
            return False, 0.0

        if object_id not in zone_state:
            zone_state[object_id] = {
                "enter_time": now,
                "last_seen_time": now,
                "last_alarm_time": None,
            }
            return False, 0.0

        state = zone_state[object_id]
        state["last_seen_time"] = now
        duration = now - state["enter_time"]
        if duration < stay_seconds:
            return False, duration

        last_alarm = state["last_alarm_time"]
        if last_alarm is None or (now - last_alarm) >= self.alarm_cooldown_seconds:
            state["last_alarm_time"] = now
            return True, duration
        return False, duration

    def cleanup_expired_states(self, timeout_seconds=10.0):
        now = time.time()
        for zone_id, zone_state in list(self.entered_at.items()):
            for object_id, state in list(zone_state.items()):
                if now - state["last_seen_time"] > timeout_seconds:
                    zone_state.pop(object_id, None)

    def evaluate_detection(self, detection, zones):
        center = detection.get("center")
        if not center and detection.get("bbox"):
            x, y, width, height = detection["bbox"]
            center = {"x": x + width / 2, "y": y + height / 2}

        if not center:
            return []

        hits = []
        for zone in zones:
            if not zone.enabled:
                continue
            if self.point_in_polygon(center, zone.get_points()):
                hits.append({
                    "zoneId": zone.id,
                    "zoneName": zone.name,
                    "ruleType": zone.rule_type,
                    "detection": detection,
                })
        return hits
