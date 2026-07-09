import logging

from .notification_svc import check_escalation
from .report_generator import report_generator
from .ws_handler import push_heartbeat


logger = logging.getLogger(__name__)


try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover - optional runtime dependency
    BackgroundScheduler = None


class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler() if BackgroundScheduler else None
        if self.scheduler:
            self._setup_jobs()

    @property
    def running(self):
        return bool(self.scheduler and self.scheduler.running)

    def _setup_jobs(self):
        self.scheduler.add_job(
            self._escalation_check_job,
            "interval",
            seconds=60,
            id="escalation_check",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._heartbeat_job,
            "interval",
            seconds=30,
            id="heartbeat",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._daily_report_job,
            "cron",
            hour=8,
            minute=0,
            id="daily_report",
            replace_existing=True,
        )

    def _escalation_check_job(self):
        result = check_escalation()
        if result:
            logger.info("Escalated alarms: %s", result)

    def _heartbeat_job(self):
        push_heartbeat()

    def _daily_report_job(self):
        report = report_generator.generate_daily_report()
        logger.info("Daily report generated for %s", report["reportDate"])

    def start(self):
        if not self.scheduler:
            logger.info("APScheduler is not installed; scheduler disabled")
            return
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def stop(self):
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def list_jobs(self):
        if not self.scheduler:
            return []
        return [{"id": job.id, "name": job.name} for job in self.scheduler.get_jobs()]


scheduler_svc = SchedulerService()

