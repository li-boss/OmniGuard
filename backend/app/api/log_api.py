from flask import Blueprint

from ..middleware.auth_middleware import auth_required
from ..models import AccessLog
from . import success


log_bp = Blueprint("access_logs", __name__)


@log_bp.get("")
@auth_required
def list_logs():
    logs = AccessLog.query.order_by(AccessLog.id.desc()).limit(100).all()
    return success([log.to_dict() for log in logs])
