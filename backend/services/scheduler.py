from apscheduler.schedulers.background import BackgroundScheduler


def create_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    return scheduler
