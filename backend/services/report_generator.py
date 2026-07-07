from datetime import date


def generate_daily_report(summary):
    return {
        "date": date.today().isoformat(),
        "summary": summary,
    }
