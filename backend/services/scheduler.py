import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from services.notification_svc import check_escalation
from services.report_generator import report_generator
from services.ws_handler import push_heartbeat

logger = logging.getLogger(__name__)


class SchedulerService:

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.app = None
        self._setup_jobs()

    def _setup_jobs(self):
        self.scheduler.add_job(
            self._escalation_check_job,
            'interval',
            seconds=60,
            id='escalation_check',
            replace_existing=True,
        )

        self.scheduler.add_job(
            self._heartbeat_job,
            'interval',
            seconds=30,
            id='heartbeat',
            replace_existing=True,
        )

        self.scheduler.add_job(
            self._daily_report_job,
            'cron',
            hour=8,
            minute=0,
            id='daily_report',
            replace_existing=True,
        )

    def _escalation_check_job(self):
        if not self.app:
            return
        with self.app.app_context():
            try:
                result = check_escalation()
                if result:
                    logger.info('Escalation check: escalated alarms %s', result)
            except Exception as e:
                logger.error('Escalation check job failed: %s', str(e))

    def _heartbeat_job(self):
        try:
            push_heartbeat()
        except Exception as e:
            logger.error('Heartbeat job failed: %s', str(e))

    def _daily_report_job(self):
        if not self.app:
            return
        with self.app.app_context():
            try:
                report = report_generator.generate_daily_report()
                markdown = report_generator.format_report_markdown(report)
                logger.info('Daily report generated:\n%s', markdown[:200])
            except Exception as e:
                logger.error('Daily report job failed: %s', str(e))

    def start(self, app):
        self.app = app
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info('Scheduler started')

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info('Scheduler stopped')


scheduler_svc = SchedulerService()
