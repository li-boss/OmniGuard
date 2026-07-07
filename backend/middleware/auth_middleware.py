from functools import wraps

from flask_jwt_extended import get_jwt, verify_jwt_in_request


def role_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            role = get_jwt().get("role")
            if roles and role not in roles:
                return {"message": "Forbidden"}, 403
            return func(*args, **kwargs)

        return wrapper

    return decorator
