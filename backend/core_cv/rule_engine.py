import time
import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self):
        # entered_at: zone_id -> { object_id: { "enter_time": ts, "last_seen_time": ts, "last_alarm_time": ts, "entry_alarm_triggered": bool, "stay_alarm_triggered": bool, "last_box_norm": [...] } }
        self.entered_at = defaultdict(dict)
        # recently_left: zone_id -> { old_object_id: { "left_time": ts, "enter_time": ts, "entry_alarm_triggered": bool, "stay_alarm_triggered": bool, "last_alarm_time": ts, "last_box_norm": [...] } }
        self.recently_left = defaultdict(dict)
        self._lock = threading.Lock()

    def point_in_polygon(self, point, polygon):
        if not polygon:
            return False
        x, y = point
        inside = False
        n = len(polygon)
        j = n - 1
        for i in range(n):
            p_i = polygon[i]
            xi = p_i.get("x", 0.0) if isinstance(p_i, dict) else p_i[0]
            yi = p_i.get("y", 0.0) if isinstance(p_i, dict) else p_i[1]
            p_j = polygon[j]
            xj = p_j.get("x", 0.0) if isinstance(p_j, dict) else p_j[0]
            yj = p_j.get("y", 0.0) if isinstance(p_j, dict) else p_j[1]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
                inside = not inside
            j = i
        return inside

    def get_center(self, box_norm):
        x1, y1, x2, y2 = box_norm
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def get_bottom_center(self, box_norm):
        x1, y1, x2, y2 = box_norm
        return ((x1 + x2) / 2.0, y2)

    def box_in_polygon_ratio(self, box_norm, polygon):
        x1, y1, x2, y2 = box_norm
        points = []
        for i in range(3):
            for j in range(3):
                points.append((
                    x1 + (x2 - x1) * (i + 1) / 4.0,
                    y1 + (y2 - y1) * (j + 1) / 4.0,
                ))
        return sum(1 for p in points if self.point_in_polygon(p, polygon)) / len(points)

    def _try_inherit_state(self, object_id, box_norm, zone_id, now):
        """Try to inherit state from a recently-left or recently-lost object with nearby position.
        
        When tracker ID jitter causes a person to be briefly lost and re-assigned,
        this matches the new object to the old one by center-distance, preserving
        enter_time, entry_alarm_triggered, and stay_alarm_triggered continuity.
        
        Returns: True if state was inherited, False otherwise.
        """
        new_cx = (box_norm[0] + box_norm[2]) / 2.0
        new_cy = (box_norm[1] + box_norm[3]) / 2.0
        
        best_match_id = None
        best_match_source = None  # 'recently_left' or 'entered_at'
        best_distance = float('inf')
        
        # 1. Search recently_left
        candidates_left = self.recently_left.get(zone_id, {})
        for old_id, old_state in list(candidates_left.items()):
            if now - old_state["left_time"] > 3.0:
                continue
            old_box = old_state.get("last_box_norm")
            if old_box is None:
                continue
            old_cx = (old_box[0] + old_box[2]) / 2.0
            old_cy = (old_box[1] + old_box[3]) / 2.0
            dist = ((new_cx - old_cx) ** 2 + (new_cy - old_cy) ** 2) ** 0.5
            if dist < 0.35 and dist < best_distance:
                best_distance = dist
                best_match_id = old_id
                best_match_source = 'recently_left'
                
        # 2. Search entered_at (stale candidates that haven't been updated in this frame/recent frame)
        candidates_entered = self.entered_at.get(zone_id, {})
        for old_id, old_state in list(candidates_entered.items()):
            if old_id == object_id:
                continue
            if now - old_state["last_seen_time"] > 0.05:
                old_box = old_state.get("last_box_norm")
                if old_box is None:
                    continue
                old_cx = (old_box[0] + old_box[2]) / 2.0
                old_cy = (old_box[1] + old_box[3]) / 2.0
                dist = ((new_cx - old_cx) ** 2 + (new_cy - old_cy) ** 2) ** 0.5
                if dist < 0.35 and dist < best_distance:
                    best_distance = dist
                    best_match_id = old_id
                    best_match_source = 'entered_at'
                    
        if best_match_id is not None:
            if best_match_source == 'recently_left':
                old_state = candidates_left.pop(best_match_id)
                time_outside = now - old_state["left_time"]
                
                # If they were outside the zone for > 1.0 second, reset their alarm states
                if time_outside > 1.0:
                    entry_alarm_triggered = False
                    stay_alarm_triggered = False
                    enter_time = now
                    last_alarm_time = None
                else:
                    entry_alarm_triggered = old_state.get("entry_alarm_triggered", False)
                    stay_alarm_triggered = old_state.get("stay_alarm_triggered", False)
                    enter_time = old_state["enter_time"]
                    last_alarm_time = old_state.get("last_alarm_time")
            else:
                old_state = candidates_entered.pop(best_match_id)
                entry_alarm_triggered = old_state.get("entry_alarm_triggered", False)
                stay_alarm_triggered = old_state.get("stay_alarm_triggered", False)
                enter_time = old_state["enter_time"]
                last_alarm_time = old_state.get("last_alarm_time")
                
            self.entered_at[zone_id][object_id] = {
                "enter_time": enter_time,
                "last_seen_time": now,
                "last_alarm_time": last_alarm_time,
                "entry_alarm_triggered": entry_alarm_triggered,
                "stay_alarm_triggered": stay_alarm_triggered,
                "last_box_norm": list(box_norm),
            }
            logger.debug(f"Inherited zone state from {best_match_source}: {best_match_id} -> {object_id} (dist={best_distance:.3f})")
            return True
            
        return False

    def evaluate_entry(self, object_id, box_norm, zone):
        """Evaluate if an object has entered the zone."""
        with self._lock:
            zone_id = zone["id"]
            point = self.get_center(box_norm)
            now = time.time()
            zone_state = self.entered_at[zone_id]
            
            if not self.point_in_polygon(point, zone["polygon"]):
                # Object left the zone, save state for possible inheritance
                if object_id in zone_state:
                    old_state = zone_state.pop(object_id)
                    self.recently_left[zone_id][object_id] = {
                        "left_time": now,
                        "enter_time": old_state["enter_time"],
                        "entry_alarm_triggered": old_state.get("entry_alarm_triggered", False),
                        "stay_alarm_triggered": old_state.get("stay_alarm_triggered", False),
                        "last_alarm_time": old_state.get("last_alarm_time"),
                        "last_box_norm": old_state.get("last_box_norm"),
                    }
                return False
                
            if object_id not in zone_state:
                # Try to inherit state from a recently-left or recently-lost object
                if not self._try_inherit_state(object_id, box_norm, zone_id, now):
                    # First time entering — new state
                    zone_state[object_id] = {
                        "enter_time": now,
                        "last_seen_time": now,
                        "last_alarm_time": None,
                        "entry_alarm_triggered": True,
                        "stay_alarm_triggered": False,
                        "last_box_norm": list(box_norm),
                    }
                    return True
                else:
                    zone_state[object_id]["last_seen_time"] = now
                    zone_state[object_id]["last_box_norm"] = list(box_norm)
                    if not zone_state[object_id].get("entry_alarm_triggered", False):
                        zone_state[object_id]["entry_alarm_triggered"] = True
                        return True
                    return False
            else:
                state = zone_state[object_id]
                state["last_seen_time"] = now
                state["last_box_norm"] = list(box_norm)
                if not state.get("entry_alarm_triggered", False):
                    state["entry_alarm_triggered"] = True
                    return True
                return False

    def evaluate_stay(self, object_id, box_norm, zone):
        """Evaluate if an object has stayed in the zone for longer than stay_seconds.
        Enforces a 30s stay alarm cooldown per object.
        """
        with self._lock:
            zone_id = zone["id"]
            stay_seconds = zone.get("stay_seconds", 5)
            point = self.get_center(box_norm)
            now = time.time()
            zone_state = self.entered_at[zone_id]
            
            # Check if point is inside the zone's polygon
            if not self.point_in_polygon(point, zone["polygon"]):
                # Object left the zone, save state for possible inheritance
                if object_id in zone_state:
                    old_state = zone_state.pop(object_id)
                    self.recently_left[zone_id][object_id] = {
                        "left_time": now,
                        "enter_time": old_state["enter_time"],
                        "entry_alarm_triggered": old_state.get("entry_alarm_triggered", False),
                        "stay_alarm_triggered": old_state.get("stay_alarm_triggered", False),
                        "last_alarm_time": old_state.get("last_alarm_time"),
                        "last_box_norm": old_state.get("last_box_norm"),
                    }
                return False, 0.0
                
            # Object is in the zone
            if object_id not in zone_state:
                # Try to inherit state from a recently-left or recently-lost object
                if not self._try_inherit_state(object_id, box_norm, zone_id, now):
                    # First time entering — new state
                    zone_state[object_id] = {
                        "enter_time": now,
                        "last_seen_time": now,
                        "last_alarm_time": None,
                        "entry_alarm_triggered": False,
                        "stay_alarm_triggered": False,
                        "last_box_norm": list(box_norm),
                    }
                    return False, 0.0
                # else: inherited, fall through to duration check
            
            # Update last seen time and box
            state = zone_state[object_id]
            state["last_seen_time"] = now
            state["last_box_norm"] = list(box_norm)
            duration = now - state["enter_time"]
            
            # Check if duration exceeds threshold
            if duration >= stay_seconds:
                # If stay alarm was not triggered yet in this stay, or if 30s has passed since the last stay alarm
                last_alarm = state.get("last_alarm_time")
                if not state.get("stay_alarm_triggered", False) or (last_alarm is not None and (now - last_alarm) >= 30.0):
                    state["stay_alarm_triggered"] = True
                    state["last_alarm_time"] = now
                    return True, duration
                else:
                    return False, duration
            else:
                return False, duration

    def cleanup_expired_states(self, timeout_seconds=10.0):
        """Remove states for objects that haven't been seen recently to prevent memory leaks."""
        with self._lock:
            now = time.time()
            for zone_id, zone_state in list(self.entered_at.items()):
                for object_id, state in list(zone_state.items()):
                    if now - state["last_seen_time"] > timeout_seconds:
                        zone_state.pop(object_id, None)
                        logger.debug(f"Cleaned up expired state for object {object_id} in zone {zone_id}")
            
            # Clean up recently_left entries older than timeout
            for zone_id, left_objects in list(self.recently_left.items()):
                for obj_id, state in list(left_objects.items()):
                    if now - state["left_time"] > timeout_seconds:
                        left_objects.pop(obj_id, None)
                if not left_objects:
                    self.recently_left.pop(zone_id, None)
