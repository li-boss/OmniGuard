from flask import Blueprint, jsonify, request

from models import AlertZone, db

rule_bp = Blueprint("rule_api", __name__)
camera_bp = Blueprint("camera_api", __name__)


@camera_bp.get("/status")
def get_cameras_status():
    from core_cv.pipeline import CameraPipelineManager
    manager = CameraPipelineManager()
    status_list = []
    
    # We lock to read pipelines safely
    with manager._lock:
        for camera_id, pipeline in manager.pipelines.items():
            status_list.append({
                "camera_id": camera_id,
                "cameraId": camera_id,
                "url": str(pipeline.url),
                "connected": pipeline.stream_manager.connected,
                "consecutive_failures": pipeline.stream_manager.consecutive_failures,
                "zones_count": len(pipeline.zones)
            })
            
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": status_list
    })


@rule_bp.get("")
def list_zones():
    camera_id = request.args.get("camera_id") or request.args.get("cameraId")
    query = AlertZone.query
    if camera_id:
        query = query.filter_by(camera_id=camera_id)
    zones = query.order_by(AlertZone.id.desc()).all()
    
    # B frontend expects a direct list of zones in some endpoints, but we also wrap it
    # Wait, does B's store wrap it or get result.data?
    # B's api/zone.js does:
    # export function getZones(params) { return request.get('/zones', { params }) }
    # And store/camera.js does:
    # const result = await zoneApi.getZones({ cameraId })
    # this.zones = result.data
    # So yes, it expects result.data to be the list of zones!
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": [serialize_zone(zone) for zone in zones]
    })


@rule_bp.post("")
def create_zone():
    payload = request.get_json() or {}
    
    # Map camelCase to snake_case for database insertion
    camera_id = payload.get("camera_id") or payload.get("cameraId", "cam-1")
    name = payload.get("name", "未命名防区")
    points = payload.get("polygon") or payload.get("points", [])
    rule_type = payload.get("rule_type") or payload.get("ruleType", "intrusion")
    distance_threshold = payload.get("distance_threshold", 0.0)
    stay_seconds = payload.get("stay_seconds") or payload.get("staySeconds", 5)
    enabled = payload.get("enabled", True)
    
    # Normalize polygon points
    normalized_polygon = normalize_polygon(points)
    
    zone = AlertZone(
        camera_id=camera_id,
        name=name,
        polygon=normalized_polygon,
        rule_type=rule_type,
        distance_threshold=distance_threshold,
        stay_seconds=stay_seconds,
        enabled=enabled
    )
    db.session.add(zone)
    db.session.commit()
    
    # Mark dirty to trigger configuration reload in background thread
    from core_cv.pipeline import CameraPipelineManager
    CameraPipelineManager().mark_dirty(zone.camera_id)
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_zone(zone)
    }), 201


@rule_bp.put("/<int:zone_id>")
def update_zone(zone_id):
    zone = AlertZone.query.get_or_404(zone_id)
    payload = request.get_json() or {}
    
    if "name" in payload:
        zone.name = payload["name"]
    if "polygon" in payload or "points" in payload:
        points = payload.get("polygon") or payload.get("points")
        zone.polygon = normalize_polygon(points)
    if "rule_type" in payload or "ruleType" in payload:
        zone.rule_type = payload.get("rule_type") or payload.get("ruleType")
    if "distance_threshold" in payload:
        zone.distance_threshold = payload["distance_threshold"]
    if "stay_seconds" in payload or "staySeconds" in payload:
        zone.stay_seconds = payload.get("stay_seconds") or payload.get("staySeconds")
    if "enabled" in payload:
        zone.enabled = payload["enabled"]
        
    db.session.commit()
    
    # Mark dirty to trigger configuration reload in background thread
    from core_cv.pipeline import CameraPipelineManager
    CameraPipelineManager().mark_dirty(zone.camera_id)
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_zone(zone)
    })


@rule_bp.delete("/<int:zone_id>")
def delete_zone(zone_id):
    zone = AlertZone.query.get_or_404(zone_id)
    camera_id = zone.camera_id
    db.session.delete(zone)
    db.session.commit()
    
    # Mark dirty to trigger configuration reload in background thread
    from core_cv.pipeline import CameraPipelineManager
    CameraPipelineManager().mark_dirty(camera_id)
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": None
    })


def normalize_polygon(points):
    normalized = []
    for p in (points or []):
        px = p.get("x", 0.0)
        py = p.get("y", 0.0)
        # Scale down if coordinate values are pixel-based
        if px > 1.0 or py > 1.0:
            px = round(px / 800.0, 6)
            py = round(py / 450.0, 6)
        normalized.append({"x": px, "y": py})
    return normalized


def serialize_zone(zone):
    pixel_points = []
    for p in (zone.polygon or []):
        px = p.get("x", 0.0)
        py = p.get("y", 0.0)
        # Restore to 800x450 canvas pixel coordinates if normalized
        pixel_points.append({
            "x": int(px * 800) if px <= 1.0 else int(px),
            "y": int(py * 450) if py <= 1.0 else int(py)
        })
        
    return {
        "id": zone.id,
        "camera_id": zone.camera_id,
        "cameraId": zone.camera_id,
        "name": zone.name,
        "rule_type": zone.rule_type or "intrusion",
        "ruleType": zone.rule_type or "intrusion",
        "polygon": zone.polygon,
        "points": pixel_points,
        "distance_threshold": zone.distance_threshold,
        "stay_seconds": zone.stay_seconds,
        "staySeconds": zone.stay_seconds,
        "enabled": zone.enabled,
    }
