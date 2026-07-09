from flask import Blueprint, request

from ..extensions import db
from ..middleware.auth_middleware import auth_required
from ..models import Zone
from . import error, success


zone_bp = Blueprint("zones", __name__)


def _validate_points(points):
    if not isinstance(points, list) or len(points) < 3:
        return False
    return all("x" in point and "y" in point for point in points)


def _mark_camera_dirty(camera_id):
    try:
        from ..core_cv.pipeline import CameraPipelineManager

        CameraPipelineManager().mark_dirty(camera_id)
    except Exception:
        pass


@zone_bp.get("")
@auth_required
def list_zones():
    camera_id = request.args.get("camera_id") or request.args.get("cameraId")
    query = Zone.query
    if camera_id:
        query = query.filter_by(camera_id=str(camera_id))
    zones = query.order_by(Zone.id.desc()).all()
    return success([zone.to_dict() for zone in zones])


@zone_bp.post("")
@auth_required
def create_zone():
    payload = request.get_json(silent=True) or {}
    camera_id = str(payload.get("cameraId") or payload.get("camera_id") or "default").strip()
    name = str(payload.get("name") or "unnamed zone").strip()
    rule_type = str(payload.get("ruleType") or payload.get("rule_type") or "intrusion").strip()
    points = payload.get("points") or payload.get("polygon")

    if not _validate_points(points):
        return error("points must contain at least 3 {x,y} items", 400)

    zone = Zone(
        camera_id=camera_id,
        name=name,
        rule_type=rule_type,
        stay_seconds=int(payload.get("staySeconds") or payload.get("stay_seconds") or 5),
    )
    zone.set_points(points)
    db.session.add(zone)
    db.session.commit()
    _mark_camera_dirty(camera_id)
    return success(zone.to_dict(), "zone created", 201)


@zone_bp.put("/<int:zone_id>")
@auth_required
def update_zone(zone_id):
    zone = db.get_or_404(Zone, zone_id)
    payload = request.get_json(silent=True) or {}
    if "cameraId" in payload:
        zone.camera_id = str(payload["cameraId"])
    if "camera_id" in payload:
        zone.camera_id = str(payload["camera_id"])
    if "name" in payload:
        zone.name = str(payload["name"]).strip()
    if "ruleType" in payload:
        zone.rule_type = str(payload["ruleType"]).strip()
    if "rule_type" in payload:
        zone.rule_type = str(payload["rule_type"]).strip()
    if "enabled" in payload:
        zone.enabled = bool(payload["enabled"])
    if "staySeconds" in payload or "stay_seconds" in payload:
        zone.stay_seconds = int(payload.get("staySeconds") or payload.get("stay_seconds") or zone.stay_seconds)

    points = payload.get("points") or payload.get("polygon")
    if points is not None:
        if not _validate_points(points):
            return error("points must contain at least 3 {x,y} items", 400)
        zone.set_points(points)

    db.session.commit()
    _mark_camera_dirty(zone.camera_id)
    return success(zone.to_dict(), "zone updated")


@zone_bp.delete("/<int:zone_id>")
@auth_required
def delete_zone(zone_id):
    zone = db.get_or_404(Zone, zone_id)
    camera_id = zone.camera_id
    db.session.delete(zone)
    db.session.commit()
    _mark_camera_dirty(camera_id)
    return success(message="zone deleted")
