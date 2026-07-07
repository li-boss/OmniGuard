import time
import logging
from collections import defaultdict

try:
    from config import Config
    ALARM_COOLDOWN_SECONDS = getattr(Config, "ALARM_COOLDOWN_SECONDS", 30)
except ImportError:
    ALARM_COOLDOWN_SECONDS = 30

logger = logging.getLogger(__name__)

class RuleEngine:
    def __init__(self):
        # entered_at: zone_id -> { object_id: { "enter_time": ts, "last_seen_time": ts, "last_alarm_time": ts or None } }
        self.entered_at = defaultdict(dict)

    def point_in_polygon(self, point, polygon):
        """
        Check if a point (x, y) is inside a polygon.
        point: tuple of (x, y) normalized coordinates.
        polygon: list of points, each point can be {"x": float, "y": float} or [float, float].
        """
        if not polygon:
            return False
            
        x, y = point
        inside = False
        n = len(polygon)
        j = n - 1
        
        for i in range(n):
            # Parse current point
            p_i = polygon[i]
            if isinstance(p_i, dict):
                xi, yi = p_i.get("x", 0.0), p_i.get("y", 0.0)
            else:
                xi, yi = p_i[0], p_i[1]
                
            # Parse previous point
            p_j = polygon[j]
            if isinstance(p_j, dict):
                xj, yj = p_j.get("x", 0.0), p_j.get("y", 0.0)
            else:
                xj, yj = p_j[0], p_j[1]
                
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i
            
        return inside

    def get_bottom_center(self, box_norm):
        """Calculate the bottom-center of a normalized box [x1, y1, x2, y2]."""
        x1, y1, x2, y2 = box_norm
        return ((x1 + x2) / 2.0, y2)

    def evaluate_stay(self, object_id, box_norm, zone):
        """
        Evaluate if an object has stayed in the zone for longer than stay_seconds.
        Returns: (should_trigger_alarm, duration_seconds)
        """
        zone_id = zone["id"]
        stay_seconds = zone.get("stay_seconds", 5)
        point = self.get_bottom_center(box_norm)
        
        now = time.time()
        zone_state = self.entered_at[zone_id]
        
        # Check if point is inside the zone's polygon
        if not self.point_in_polygon(point, zone["polygon"]):
            # Object left the zone, clear its state
            zone_state.pop(object_id, None)
            return False, 0.0
            
        # Object is in the zone
        if object_id not in zone_state:
            # First time entering
            zone_state[object_id] = {
                "enter_time": now,
                "last_seen_time": now,
                "last_alarm_time": None
            }
            return False, 0.0
        else:
            # Update last seen time
            state = zone_state[object_id]
            state["last_seen_time"] = now
            duration = now - state["enter_time"]
            
            # Check if duration exceeds threshold
            if duration >= stay_seconds:
                last_alarm = state["last_alarm_time"]
                if last_alarm is None or (now - last_alarm) >= ALARM_COOLDOWN_SECONDS:
                    # Trigger alarm (first time or after cooldown)
                    state["last_alarm_time"] = now
                    return True, duration
                else:
                    # Within cooldown, suppress duplicate alarm
                    return False, duration
            else:
                return False, duration

    def cleanup_expired_states(self, timeout_seconds=10.0):
        """Remove states for objects that haven't been seen recently to prevent memory leaks."""
        now = time.time()
        for zone_id, zone_state in list(self.entered_at.items()):
            for object_id, state in list(zone_state.items()):
                if now - state["last_seen_time"] > timeout_seconds:
                    zone_state.pop(object_id, None)
                    logger.debug(f"Cleaned up expired state for object {object_id} in zone {zone_id}")
