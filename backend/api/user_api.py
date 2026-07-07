from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from models import User, db

user_bp = Blueprint("user_api", __name__)


@user_bp.post("/register")
def register():
    payload = request.get_json() or {}
    user = User(username=payload["username"], role=payload.get("role", "operator"))
    user.set_password(payload["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username, "role": user.role}), 201


@user_bp.post("/login")
def login():
    payload = request.get_json() or {}
    user = User.query.filter_by(username=payload.get("username")).first()
    if not user or not user.check_password(payload.get("password", "")):
        return jsonify({"message": "Invalid username or password"}), 401
    token = create_access_token(identity=str(user.id))
    return jsonify({
        "access_token": token,
        "user": {"id": user.id, "username": user.username, "role": user.role},
    })


@user_bp.get("/profile")
@jwt_required()
def profile():
    user = User.query.get_or_404(int(get_jwt_identity()))
    return jsonify({"id": user.id, "username": user.username, "role": user.role})


@user_bp.post("/refresh")
@jwt_required()
def refresh():
    return jsonify({"access_token": create_access_token(identity=get_jwt_identity())})
