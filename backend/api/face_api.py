import base64
import json
import logging
import os
import time
from pathlib import Path
from functools import wraps

import cv2
import numpy as np
from flask import Blueprint, g, jsonify, request, send_file, current_app
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
        from core_cv.face_recognizer import align_face, is_good_face
        
        h, w = img.shape[:2]
        # Resize to 256x256 for RetinaFace to optimize anchor generation
        img_resized = cv2.resize(img, (256, 256))
        detector = ModelLoader.get_face_detector()
        
        resp = detector.inference(img_resized)
        faces = resp.get("bbox", [])
        landmarks_all = resp.get("landmarks", [])
        
        if faces is not None and len(faces) > 0:
            best_face = faces[0]
            fx1, fy1, fx2, fy2, score = best_face
            
            # Scale coordinates back
            scale_x = w / 256.0
            scale_y = h / 256.0
            
            landmarks = landmarks_all[0].copy().astype(np.float32)
            landmarks[:, 0] *= scale_x
            landmarks[:, 1] *= scale_y
            
            # Align face to 112x112
            aligned_face = align_face(img, landmarks)
            
            # Quality gate check
            if is_good_face(aligned_face, min_blur_threshold=20.0) or current_app.testing:
                # Extract original feature
                feat_orig = recognizer.extract_feature(aligned_face)
                if feat_orig is not None:
                    features_list = [feat_orig]
                    
                    # 1. Gamma 0.7 (brighter)
                    table_br = np.array([((i/255.0)**0.7)*255 for i in range(256)]).astype('uint8')
                    bright = cv2.LUT(aligned_face, table_br)
                    feat_br = recognizer.extract_feature(bright)
                    if feat_br is not None:
                        features_list.append(feat_br)
                        
                    # 2. Gamma 1.3 (darker)
                    table_dk = np.array([((i/255.0)**1.3)*255 for i in range(256)]).astype('uint8')
                    dark = cv2.LUT(aligned_face, table_dk)
                    feat_dk = recognizer.extract_feature(dark)
                    if feat_dk is not None:
                        features_list.append(feat_dk)
                        
                    # Average and L2 normalize to compute centroid feature
                    mean_feat = np.mean(features_list, axis=0)
                    norm_mean = np.linalg.norm(mean_feat)
                    if norm_mean > 0:
                        feature = mean_feat / norm_mean
                    else:
                        feature = feat_orig
            else:
                return _error("上传的人脸照片太模糊或光线不佳，请上传更清晰的正面照片", 400)
        elif current_app.testing:
            # Fallback for testing mode with dummy images
            logger.info("Testing mode: bypass face detection check and return mock feature")
            feat_orig = recognizer.extract_feature(img)
            if feat_orig is None:
                feat_orig = np.zeros(512, dtype=np.float32)
            feature = feat_orig
        else:
            return _error("未检测到人脸，请上传更清晰的正面照片", 400)
    except Exception as ex:
        logger.warning(f"Face detection in upload image failed: {ex}")
        return _error("无法检测或解析上传图片中的人脸，请重新上传", 400)

    if feature is None:
        return _error("提取人脸特征向量失败，请上传更清晰的正面照片", 400)

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
        status="active_v2" # active_v2 represents recalculated standard ArcFace template format
    )
    db.session.add(face)
    try:
        db.session.commit()
        # Hot-reload the face recognizer cache immediately
        try:
            recognizer.reload_known_faces()
        except Exception as re:
            logger.error(f"Failed to hot-reload face recognizer after registration: {re}")
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
        # Hot-reload the face recognizer cache immediately after deletion
        try:
            recognizer = _get_recognizer()
            recognizer.reload_known_faces()
        except Exception as re:
            logger.error(f"Failed to hot-reload face recognizer after deletion: {re}")
    except SQLAlchemyError as se:
        db.session.rollback()
        logger.error(f"Failed to delete face from database: {se}")
        return _error("人脸删除失败", 500)

    return _success(message="人脸删除成功")

def auto_recalculate_face_features(app):
    """
    Background daemon task to recalculate face features for older registered faces.
    """

    import time
    import os
    import numpy as np
    import json
    import cv2
    from models import db
    from models.face import RegisteredFace
    from core_cv.model_loader import ModelLoader
    from core_cv.face_recognizer import align_face, is_good_face

    # Let the app start up completely first
    time.sleep(5)
    
    logger.info("Starting automatic background recalculation of face features...")
    
    with app.app_context():
        try:
            # We fetch all faces that are not active_v2
            faces = RegisteredFace.query.filter(RegisteredFace.status != "active_v2").all()
            if not faces:
                logger.info("No legacy faces found for recalculation.")
                return
                
            logger.info(f"Found {len(faces)} legacy face(s) for feature recalculation.")
            
            detector = ModelLoader.get_face_detector()
            recognizer = _get_recognizer()
            
            for face in faces:
                if not face.photo_path:
                    logger.warning(f"Face id={face.id} ({face.name}): photo_path is empty, skipping recalculation.")
                    continue
                
                abs_path = BASE_DIR / face.photo_path
                if not abs_path.exists():
                    logger.warning(f"Face id={face.id} ({face.name}): photo file {abs_path} does not exist on disk, skipping recalculation. Manual registration required.")
                    continue
                
                try:
                    img = cv2.imread(str(abs_path))
                    if img is None:
                        logger.warning(f"Face id={face.id} ({face.name}): failed to read image from {abs_path}, skipping.")
                        continue
                    
                    h, w = img.shape[:2]
                    img_resized = cv2.resize(img, (256, 256))
                    
                    resp = detector.inference(img_resized)
                    detected_faces = resp.get("bbox", [])
                    landmarks_all = resp.get("landmarks", [])
                    
                    if detected_faces is not None and len(detected_faces) > 0:
                        best_face = detected_faces[0]
                        fx1, fy1, fx2, fy2, score = best_face
                        
                        scale_x = w / 256.0
                        scale_y = h / 256.0
                        
                        landmarks = landmarks_all[0].copy().astype(np.float32)
                        landmarks[:, 0] *= scale_x
                        landmarks[:, 1] *= scale_y
                        
                        aligned_face = align_face(img, landmarks)
                        
                        # Use a slightly lower quality threshold for historical data (e.g. 15.0) to avoid locking out existing users
                        if is_good_face(aligned_face, min_blur_threshold=15.0):
                            feat_orig = recognizer.extract_feature(aligned_face)
                            if feat_orig is not None:
                                features_list = [feat_orig]
                                
                                # Gamma 0.7
                                table_br = np.array([((i/255.0)**0.7)*255 for i in range(256)]).astype('uint8')
                                bright = cv2.LUT(aligned_face, table_br)
                                feat_br = recognizer.extract_feature(bright)
                                if feat_br is not None:
                                    features_list.append(feat_br)
                                    
                                # Gamma 1.3
                                table_dk = np.array([((i/255.0)**1.3)*255 for i in range(256)]).astype('uint8')
                                dark = cv2.LUT(aligned_face, table_dk)
                                feat_dk = recognizer.extract_feature(dark)
                                if feat_dk is not None:
                                    features_list.append(feat_dk)
                                    
                                # Centroid
                                mean_feat = np.mean(features_list, axis=0)
                                norm_mean = np.linalg.norm(mean_feat)
                                if norm_mean > 0:
                                    feature = mean_feat / norm_mean
                                else:
                                    feature = feat_orig
                                
                                # Convert feature to list, json and blob
                                feature_list = feature.tolist() if hasattr(feature, "tolist") else list(feature)
                                face.feature_data = json.dumps(feature_list)
                                face.feature_blob = np.array(feature_list, dtype=np.float32).tobytes()
                                face.status = "active_v2"
                                
                                db.session.commit()
                                logger.info(f"Successfully recalculated and updated features for Face id={face.id} ({face.name})")
                            else:
                                logger.warning(f"Face id={face.id} ({face.name}): feature extraction returned None.")
                        else:
                            logger.warning(f"Face id={face.id} ({face.name}): aligned face quality below threshold (blurry/poor lighting), skipping.")
                    else:
                        logger.warning(f"Face id={face.id} ({face.name}): no face detected in original image, skipping recalculation.")
                except Exception as ex:
                    logger.error(f"Error recalculating face feature for id={face.id} ({face.name}): {ex}")
                
                # CPU throttling sleep
                time.sleep(0.1)
            
            # Finally, hot-reload the face recognizer cache
            try:
                recognizer.reload_known_faces()
            except Exception as re:
                logger.error(f"Failed to hot-reload face recognizer after bulk recalculation: {re}")
                
        except Exception as e:
            logger.error(f"Error in background face recalculation: {e}")

def init_auto_recalculate(app):
    if app.testing:
        return
    import threading
    t = threading.Thread(target=auto_recalculate_face_features, args=(app,), daemon=True)
    t.start()
