from flask import Blueprint, request

from ..core_cv.face_recognizer import FaceRecognizer, SFACE_FEATURE_DIM
from ..extensions import db
from ..middleware.auth_middleware import auth_required
from ..models import FaceRecord
from . import error, success


face_bp = Blueprint("faces", __name__)
face_recognizer = FaceRecognizer()


def _normalize_features(value):
    if _is_feature_vector(value):
        return [[round(float(item), 8) for item in value]]
    if isinstance(value, list):
        return [
            [round(float(item), 8) for item in feature]
            for feature in value
            if _is_feature_vector(feature)
        ]
    return []


def _is_feature_vector(value):
    return (
        isinstance(value, list)
        and len(value) == SFACE_FEATURE_DIM
        and all(isinstance(item, (int, float)) for item in value)
    )


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

    features = (
        _normalize_features(feature_data)
        if feature_data is not None
        else face_recognizer.extract_features(image, allow_fallback=False)
    )
    if not features:
        return error(
            "No clear frontal face was detected in the image. Please upload a brighter, sharper face photo.",
            422,
            {"reason": "face_not_detected", "model": face_recognizer.model_name},
        )
    invalid = [len(feature) for feature in features if len(feature) != SFACE_FEATURE_DIM]
    if invalid:
        return error(
            "Face feature dimension is incompatible with the current SFace model.",
            422,
            {"reason": "feature_dimension_mismatch", "expected": SFACE_FEATURE_DIM, "actual": invalid[0]},
        )

    face = FaceRecord.query.filter_by(student_id=student_id).first()
    if face is None:
        face = FaceRecord(student_id=student_id, name=name)
        db.session.add(face)

    face.name = name
    if image:
        face.image_preview = image if image.startswith("data:") else f"data:image/jpeg;base64,{image}"
    added = face.add_features(features)
    db.session.commit()
    data = face.to_dict()
    data["addedSamples"] = added
    return success(data, "face registered", 201)


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
                "features": face.get_features(),
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
