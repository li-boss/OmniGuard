from flask import Blueprint, jsonify, request

from models import AlertZone, db

rule_bp = Blueprint("rule_api", __name__)


@rule_bp.get("")
def list_zones():
    camera_id = request.args.get("camera_id")
    query = AlertZone.query
    if camera_id:
        query = query.filter_by(camera_id=camera_id)
    zones = query.order_by(AlertZone.id.desc()).all()
    return jsonify([serialize_zone(zone) for zone in zones])


@rule_bp.post("")
def create_zone():
    payload = request.get_json() or {}
    zone = AlertZone(**payload)
    db.session.add(zone)
    db.session.commit()
    return jsonify(serialize_zone(zone)), 201


@rule_bp.put("/<int:zone_id>")
def update_zone(zone_id):
    zone = AlertZone.query.get_or_404(zone_id)
    for key in ["name", "polygon", "distance_threshold", "stay_seconds", "enabled"]:
        if key in (request.get_json() or {}):
            setattr(zone, key, request.json[key])
    db.session.commit()
    return jsonify(serialize_zone(zone))


@rule_bp.delete("/<int:zone_id>")
def delete_zone(zone_id):
    zone = AlertZone.query.get_or_404(zone_id)
    db.session.delete(zone)
    db.session.commit()
    return "", 204


def serialize_zone(zone):
    return {
        "id": zone.id,
        "camera_id": zone.camera_id,
        "name": zone.name,
        "polygon": zone.polygon,
        "distance_threshold": zone.distance_threshold,
        "stay_seconds": zone.stay_seconds,
        "enabled": zone.enabled,
    }
