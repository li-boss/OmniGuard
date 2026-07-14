from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from models import User, db

auth_bp = Blueprint("auth_api", __name__)
user_bp = Blueprint("user_api", __name__)


@auth_bp.post("/register")
def register():
    payload = request.get_json() or {}
    username = payload["username"]
    password = payload["password"]
    role = payload.get("role", "operator")
    
    if User.query.filter_by(username=username).first():
        return jsonify({"code": 1, "message": "用户名已存在", "data": None}), 409
        
    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    token = create_access_token(identity=str(user.id))
    return jsonify({
        "code": 0,
        "message": "注册成功",
        "data": {
            "token": token,
            "user": {"id": user.id, "username": user.username, "role": user.role}
        }
    }), 201


@auth_bp.post("/login")
def login():
    payload = request.get_json() or {}
    username = payload.get("username")
    password = payload.get("password", "")
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"code": 1, "message": "用户名或密码错误", "data": None}), 401
        
    token = create_access_token(identity=str(user.id))
    return jsonify({
        "code": 0,
        "message": "登录成功",
        "data": {
            "token": token,
            "user": {"id": user.id, "username": user.username, "role": user.role}
        }
    })


@auth_bp.post("/refresh")
@jwt_required()
def refresh():
    token = create_access_token(identity=get_jwt_identity())
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "token": token
        }
    })


@user_bp.get("/me")
@jwt_required()
def me():
    user = User.query.get_or_404(int(get_jwt_identity()))
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {"id": user.id, "username": user.username, "role": user.role}
    })


@user_bp.put("/me/password")
@jwt_required()
def change_password():
    payload = request.get_json() or {}
    old_password = payload.get("oldPassword", "")
    new_password = payload.get("newPassword", "")
    
    user = User.query.get_or_404(int(get_jwt_identity()))
    if not user.check_password(old_password):
        return jsonify({"code": 1, "message": "旧密码错误", "data": None}), 400
        
    if len(new_password) < 6:
        return jsonify({"code": 1, "message": "新密码长度至少为 6 位", "data": None}), 400
        
    user.set_password(new_password)
    db.session.commit()
    return jsonify({
        "code": 0,
        "message": "密码修改成功",
        "data": None
    })
