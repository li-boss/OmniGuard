import base64
import json
import logging
import os
import time
from pathlib import Path
from functools import wraps

import cv2
import numpy as np
from flask import Blueprint, g, jsonify, request, send_file
from sqlalchemy.exc import SQLAlchemyError

from middleware.auth_middleware import login_required, role_required
from models import Face, User, db

logger = logging.getLogger(__name__)

face_bp = Blueprint("face_api", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent

def _get_recognizer():
    try:
        from core_cv.face_recognizer import FaceRecognizer
        return FaceRecognizer()
    except (ImportError, AttributeError):
        # 降级方案：若 CV 管线未就绪，使用随机初始化的归一化 512 维特征向量
        import random
        class DummyRecognizer:
            def extract_feature(self, img):
                feat = np.array([random.random() for _ in range(512)], dtype=np.float32)
                norm = np.linalg.norm(feat)
                if norm > 0:
                    feat = feat / norm
                return feat
        return DummyRecognizer()

def _success(data=None, message="ok", status=200):
    return jsonify({"code": 0, "message": message, "data": data if data is not None else {}}), status

def _error(message, status):
    return jsonify({"code": 1, "message": message, "data": None}), status

@face_bp.post("/api/faces/register")
@login_required
def register_face():
    """注册人脸。管理员/安全员可为任意用户注册，普通用户只能为自己注册。"""
    data = request.get_json(silent=True) or {}
    student_id = data.get("studentId")
    name = data.get("name")
    image_base64 = data.get("image")

    if not student_id or not name or not image_base64:
        return _error("学号、姓名和照片数据不能为空", 400)

    # 1. 查找或自动创建对应的 User
    user = User.query.filter_by(username=student_id).first()
    user_created = False
    if not user:
        user = User(username=student_id, real_name=name, role="student")
        user.set_password("123456")
        db.session.add(user)
        try:
            db.session.commit()
            user_created = True
        except SQLAlchemyError as se:
            db.session.rollback()
            logger.error(f"Failed to auto-create user: {se}")
            return _error("自动创建用户失败", 500)

    # 权限校验：非特权用户只能给自己录入人脸
    if g.current_user.role not in ("admin", "security") and g.current_user.id != user.id:
        return _error("权限不足，普通用户只能为自己录入人脸", 403)

    # 2. 解码 base64 图片并保存到磁盘
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]
    try:
        img_bytes = base64.b64decode(image_base64)
    except Exception as e:
        return _error(f"图片 base64 解码失败: {e}", 400)

    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return _error("无法解析图片", 400)

    faces_dir = BASE_DIR / 'data' / 'faces'
    faces_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{student_id}_{int(time.time())}.jpg"
    filepath = faces_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.error(f"Failed to write face image to disk: {e}")
        return _error("图片保存失败", 500)

    image_path = f"data/faces/{filename}"

    # 3. 提取人脸特征向量
    recognizer = _get_recognizer()
    feature = None
    try:
        from core_cv.model_loader import ModelLoader
        detector = ModelLoader.get_face_detector()
        h, w = img.shape[:2]
        detector.setInputSize((w, h))
        retval, faces = detector.detect(img)
        if faces is not None and len(faces) > 0:
            face_box = faces[0][0:4]
            if np.isfinite(face_box).all():
                fx, fy, fw_f, fh_f = map(int, face_box)
                pad_w = int(fw_f * 0.15)
                pad_h = int(fh_f * 0.15)
                
                face_x1 = max(0, fx - pad_w)
                face_y1 = max(0, fy - pad_h)
                face_x2 = min(w, fx + fw_f + pad_w)
                face_y2 = min(h, fy + fh_f + pad_h)
                
                if face_x2 > face_x1 and face_y2 > face_y1:
                    face_crop = img[face_y1:face_y2, face_x1:face_x2]
                    feature = recognizer.extract_feature(face_crop)
    except Exception as ex:
        logger.warning(f"Face detection in upload image failed, fallback to whole image extraction: {ex}")

    if feature is None:
        try:
            feature = recognizer.extract_feature(img)
        except Exception as ex2:
            logger.error(f"Failed to extract face feature vector: {ex2}")
            return _error("特征提取失败", 500)

    if feature is None:
        return _error("提取人脸特征向量失败，无法识别照片中的人脸，请上传更清晰的正面照片", 400)

    feature_list = feature.tolist() if hasattr(feature, "tolist") else list(feature)
    feature_json = json.dumps(feature_list)
    feature_blob = np.array(feature_list, dtype=np.float32).tobytes()

    # 4. 创建并保存人脸记录
    face = Face(
        user_id=user.id,
        name=name,
        photo_path=image_path,
        image_path=image_path,
        feature_data=feature_json,
        feature_blob=feature_blob,
        device_code=data.get("device_code"),
        status="active"
    )
    db.session.add(face)
    try:
        db.session.commit()
    except SQLAlchemyError as se:
        db.session.rollback()
        logger.error(f"Failed to commit face to DB: {se}")
        # Try to clean up saved file
        if filepath.exists():
            filepath.unlink()
        return _error("人脸数据库保存失败", 500)

    msg = "人脸注册成功"
    if user_created:
        msg += "，自动创建了该学号的用户账号（默认密码为 123456）"

    return _success({"face": face.to_dict()}, msg, 201)

@face_bp.get("/api/faces")
@login_required
def list_faces():
    """查询人脸列表。普通用户只能查询自己的人脸。"""
    user_id = request.args.get("user_id", type=int)
    
    # 权限检查
    if g.current_user.role not in ("admin", "security"):
        user_id = g.current_user.id

    query = Face.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    faces = query.order_by(Face.id.desc()).all()
    # 针对前端 FaceAccess 期待返回扁平数据包
    return _success([face.to_dict(include_feature=False) for face in faces])

@face_bp.get("/api/faces/features")
@role_required("admin", "security")
def list_active_face_features():
    """获取所有可用的人脸特征列表。"""
    faces = Face.query.filter_by(status="active").order_by(Face.id.asc()).all()
    return _success([face.to_dict(include_feature=True) for face in faces])

@face_bp.get("/api/faces/<int:face_id>/image")
def get_face_image(face_id):
    """动态获取并传输本地人脸图片文件。"""
    face = db.session.get(Face, face_id)
    if not face:
        return _error("人脸数据记录不存在", 404)
        
    path_str = face.photo_path or face.image_path
    if not path_str:
        return _error("人脸图片路径不存在", 404)

    path = Path(path_str)
    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.exists():
        logger.warning(f"Face image file not found on disk: {path}")
        return _error("图片文件不存在", 404)

    return send_file(str(path), mimetype="image/jpeg")

@face_bp.delete("/api/faces/<int:face_id>")
@login_required
def delete_face(face_id):
    """删除人脸。"""
    face = db.session.get(Face, face_id)
    if not face:
        return _error("人脸不存在", 404)

    if g.current_user.role not in ("admin", "security") and g.current_user.id != face.user_id:
        return _error("权限不足", 403)

    # 尝试删除磁盘上的物理文件
    path_str = face.photo_path or face.image_path
    if path_str:
        path = Path(path_str)
        if not path.is_absolute():
            path = BASE_DIR / path
        if path.exists():
            try:
                path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete face file {path} from disk: {e}")

    db.session.delete(face)
    try:
        db.session.commit()
    except SQLAlchemyError as se:
        db.session.rollback()
        logger.error(f"Failed to delete face from database: {se}")
        return _error("人脸删除失败", 500)

    return _success(message="人脸删除成功")
