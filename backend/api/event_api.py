from flask import jsonify, request

from api import event_bp
from extensions import db
from models.alarm import AlarmEvent
from services.ws_handler import push_alarm


@event_bp.route("", methods=["GET"])
def get_alarm_list():
    """
    获取告警列表
    """

    page = request.args.get(
        "page",
        1,
        type=int
    )

    page_size = request.args.get(
        "page_size",
        20,
        type=int
    )

    alarm_type = request.args.get("type")
    severity = request.args.get("severity")
    handle_status = request.args.get("handle_status")


    query = AlarmEvent.query.order_by(
        AlarmEvent.create_time.desc()
    )


    if alarm_type:
        query = query.filter(
            AlarmEvent.alarm_type == alarm_type
        )

    if severity:
        query = query.filter(
            AlarmEvent.severity == severity
        )

    if handle_status:
        query = query.filter(
            AlarmEvent.handle_status == handle_status
        )


    result = query.paginate(
        page=page,
        per_page=page_size,
        error_out=False
    )


    return jsonify({
        "code": 200,
        "data": {
            "list": [
                item.to_dict()
                for item in result.items
            ],
            "total": result.total,
            "page": page,
            "page_size": page_size
        }
    })


@event_bp.route(
    "/<int:alarm_id>/handle",
    methods=["PUT"]
)
def handle_alarm(alarm_id):

    alarm = db.session.get(
        AlarmEvent,
        alarm_id
    )

    if alarm is None:
        return jsonify({
            "code": 404,
            "msg": "告警不存在"
        }), 404


    data = request.get_json(
        silent=True
    ) or {}


    alarm.handle_status = data.get(
        "handle_status",
        "handled"
    )

    alarm.handle_note = data.get(
        "handle_note",
        ""
    )


    db.session.commit()


    return jsonify({
        "code": 200,
        "msg": "处置成功",
        "data": alarm.to_dict()
    })



def create_alarm_record(alarm_dict):
    """
    给视觉模块调用
    创建告警
    """

    alarm = AlarmEvent(
        camera_id=alarm_dict["camera_id"],
        alarm_type=alarm_dict["alarm_type"],
        severity=alarm_dict.get(
            "severity",
            "low"
        ),
        content=alarm_dict.get(
            "content",
            ""
        ),
        handle_status="pending"
    )


    db.session.add(alarm)

    db.session.commit()


    alarm_data = alarm.to_dict()


    push_alarm(
        alarm_data
    )


    return alarm_data