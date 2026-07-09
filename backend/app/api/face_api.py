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
    page = request.args.get("page", type=int)
    page_size = request.args.get("pageSize") or request.args.get("page_size")
    query = FaceRecord.query.order_by(FaceRecord.id.desc())
    if page and page_size:
        pagination = query.paginate(page=max(page, 1), per_page=min(max(int(page_size), 1), 100), error_out=False)
        return success({
            "items": [face.to_dict() for face in pagination.items],
            "page": pagination.page,
            "pageSize": pagination.per_page,
            "page_size": pagination.per_page,
            "total": pagination.total,
        })
    faces = query.all()
    return success([face.to_dict() for face in faces])


@face_bp.post("/register")
@auth_required
def register_face():
    payload = request.get_json(silent=True) or {}
    student_id = str(payload.get("studentId") or payload.get("student_id") or payload.get("user_id") or "").strip()
    name = str(payload.get("name") or payload.get("realName") or payload.get("real_name") or student_id).strip()
    image = str(payload.get("image") or payload.get("image_path") or payload.get("face_image_url") or "").strip()
    feature_data = payload.get("featureData") or payload.get("feature_data") or payload.get("face_encoding")

    if not student_id or (not image and not feature_data):
        return error("studentId/user_id and image/feature_data are required", 400)

    feature = feature_data if feature_data is not None else face_recognizer.extract_feature(image)
    face = FaceRecord.query.filter_by(student_id=student_id).first()
    if face is None:
        face = FaceRecord(student_id=student_id, name=name)
        db.session.add(face)

    face.name = name
    if image:
        face.image_preview = image if image.startswith("data:") else f"data:image/jpeg;base64,{image}"
    face.set_feature(feature)
    db.session.commit()
    return success(face.to_dict(), "face registered", 201)


@face_bp.get("/features")
@auth_required
def list_face_features():
    faces = FaceRecord.query.order_by(FaceRecord.id.asc()).all()
    return success({
        "items": [
            {
                **face.to_dict(),
                "featureData": face.get_feature(),
                "feature_data": face.get_feature(),
            }
            for face in faces
        ],
    })


@face_bp.delete("/<int:face_id>")
@auth_required
def delete_face(face_id):
    face = db.get_or_404(FaceRecord, face_id)
    db.session.delete(face)
    db.session.commit()
    return success(message="face deleted")
