class Scheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, name, handler):
        self.jobs.append({"name": name, "handler": handler})

    def list_jobs(self):
        return [{"name": job["name"]} for job in self.jobs]


scheduler = Scheduler()
