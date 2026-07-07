from flask_apscheduler import APScheduler

from models.alarm import AlarmEvent
from services.notification_svc import check_escalation
from services.report_generator import generate_daily_report


scheduler = APScheduler()


@scheduler.task(
    "cron",
    id="daily_report",
    hour=1,
    minute=0
)
def task_daily_report():
    generate_daily_report()


@scheduler.task(
    "interval",
    id="alarm_escalate",
    minutes=5
)
def task_escalate_alarm():

    pending_list = AlarmEvent.query.filter_by(
        handle_status="pending"
    ).all()

    for alarm in pending_list:
        check_escalation(alarm.id)


def start_scheduler(app):

    scheduler.init_app(app)

    scheduler.start()

    print("APScheduler 已启动")