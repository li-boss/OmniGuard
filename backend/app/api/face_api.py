from flask import Blueprint, request

from ..core_cv.face_recognizer import FaceRecognizer
from ..extensions import db
from ..middleware.auth_middleware import auth_required
from ..models import FaceRecord
from . import error, success


face_bp = Blueprint("faces", __name__)
face_recognizer = FaceRecognizer()


@face_bp.get("")
@auth_required
def list_faces():
    faces = FaceRecord.query.order_by(FaceRecord.id.desc()).all()
    return success([face.to_dict() for face in faces])


@face_bp.post("/register")
@auth_required
def register_face():
    payload = request.get_json(silent=True) or {}
    student_id = str(payload.get("studentId") or payload.get("student_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    image = str(payload.get("image") or "").strip()

    if not student_id or not name or not image:
        return error("studentId, name and image are required", 400)

    feature = face_recognizer.extract_feature(image)
    face = FaceRecord.query.filter_by(student_id=student_id).first()
    if face is None:
        face = FaceRecord(student_id=student_id, name=name)
        db.session.add(face)

    face.name = name
    face.image_preview = image if image.startswith("data:") else f"data:image/jpeg;base64,{image}"
    face.set_feature(feature)
    db.session.commit()
    return success(face.to_dict(), "face registered", 201)


@face_bp.delete("/<int:face_id>")
@auth_required
def delete_face(face_id):
    face = db.get_or_404(FaceRecord, face_id)
    db.session.delete(face)
    db.session.commit()
    return success(message="face deleted")
