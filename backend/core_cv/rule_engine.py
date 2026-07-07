from collections import defaultdict
from datetime import datetime


class RuleEngine:
    def __init__(self):
        self.entered_at = defaultdict(dict)

    def point_in_polygon(self, point, polygon):
        x, y = point
        inside = False
        j = len(polygon) - 1
        for i, current in enumerate(polygon):
            xi, yi = current["x"], current["y"]
            xj, yj = polygon[j]["x"], polygon[j]["y"]
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def evaluate_stay(self, object_id, point, zone):
        now = datetime.utcnow()
        zone_state = self.entered_at[zone["id"]]
        if not self.point_in_polygon(point, zone["polygon"]):
            zone_state.pop(object_id, None)
            return False
        zone_state.setdefault(object_id, now)
        return (now - zone_state[object_id]).total_seconds() >= zone.get("stay_seconds", 5)
