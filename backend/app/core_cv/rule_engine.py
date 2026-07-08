class RuleEngine:
    def point_in_polygon(self, point, polygon):
        x = point["x"]
        y = point["y"]
        inside = False
        j = len(polygon) - 1
        for i, current in enumerate(polygon):
            previous = polygon[j]
            xi, yi = current["x"], current["y"]
            xj, yj = previous["x"], previous["y"]
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

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
