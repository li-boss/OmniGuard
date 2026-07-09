from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from ..extensions import db
from ..models import AlarmEvent


class ReportGenerator:
    def generate_daily_report(self, target_date=None):
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()
        elif isinstance(target_date, str):
            target_date = datetime.fromisoformat(target_date).date()

        day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        day_filter = (
            AlarmEvent.occurred_at >= day_start,
            AlarmEvent.occurred_at < day_end,
        )
        total = AlarmEvent.query.filter(*day_filter).count()
        resolved = AlarmEvent.query.filter(*day_filter, AlarmEvent.status.in_(["handled", "resolved"])).count()
        false_positive = AlarmEvent.query.filter(*day_filter, AlarmEvent.status == "false_positive").count()
        pending = AlarmEvent.query.filter(*day_filter, AlarmEvent.status.in_(["pending", "handling"])).count()

        severity_stats = (
            db.session.query(AlarmEvent.severity, func.count(AlarmEvent.id))
            .filter(*day_filter)
            .group_by(AlarmEvent.severity)
            .all()
        )
        type_stats = (
            db.session.query(AlarmEvent.event_type, func.count(AlarmEvent.id))
            .filter(*day_filter)
            .group_by(AlarmEvent.event_type)
            .all()
        )
        camera_stats = (
            db.session.query(AlarmEvent.camera_id, func.count(AlarmEvent.id))
            .filter(*day_filter)
            .group_by(AlarmEvent.camera_id)
            .order_by(func.count(AlarmEvent.id).desc())
            .limit(5)
            .all()
        )

        handled_alarms = AlarmEvent.query.filter(*day_filter, AlarmEvent.handled_at.isnot(None)).all()
        avg_handle_time = None
        if handled_alarms:
            total_seconds = sum(
                (alarm.handled_at - alarm.occurred_at).total_seconds()
                for alarm in handled_alarms
            )
            avg_handle_time = round(total_seconds / len(handled_alarms), 1)

        resolve_rate = round(resolved / total * 100, 1) if total else 0.0
        report = {
            "reportDate": target_date.isoformat(),
            "report_date": target_date.isoformat(),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "totalAlarms": total,
                "total_alarms": total,
                "resolved": resolved,
                "falsePositive": false_positive,
                "false_positive": false_positive,
                "pending": pending,
                "resolveRate": resolve_rate,
                "resolve_rate": resolve_rate,
                "avgHandleTimeSeconds": avg_handle_time,
                "avg_handle_time_seconds": avg_handle_time,
            },
            "severityDistribution": dict(severity_stats),
            "severity_distribution": dict(severity_stats),
            "typeDistribution": dict(type_stats),
            "type_distribution": dict(type_stats),
            "topCameras": [{"cameraId": camera_id, "camera_id": camera_id, "count": count} for camera_id, count in camera_stats],
            "top_cameras": [{"camera_id": camera_id, "count": count} for camera_id, count in camera_stats],
        }
        report["recommendations"] = self._generate_recommendations(
            total,
            resolve_rate,
            avg_handle_time,
            severity_stats,
        )
        return report

    def _generate_recommendations(self, total, resolve_rate, avg_handle_time, severity_stats):
        recommendations = []
        if total and resolve_rate < 80:
            recommendations.append("Alarm resolution rate is below 80%; review staffing and handling workflow.")
        if avg_handle_time and avg_handle_time > 600:
            recommendations.append("Average handling time is above 10 minutes; check notification delivery.")
        for severity, count in severity_stats:
            if severity == "critical" and count > 3:
                recommendations.append(f"{count} critical alarms occurred today; inspect the related areas.")
        if not recommendations:
            recommendations.append("System is operating normally.")
        return recommendations

    def format_report_markdown(self, report):
        summary = report["summary"]
        lines = [
            f"# Smart Campus Security Daily Report - {report['reportDate']}",
            "",
            "## Summary",
            f"- Total alarms: {summary['totalAlarms']}",
            f"- Resolved: {summary['resolved']}",
            f"- False positives: {summary['falsePositive']}",
            f"- Pending: {summary['pending']}",
            f"- Resolve rate: {summary['resolveRate']}%",
            f"- Average handling time: {summary['avgHandleTimeSeconds']} seconds",
            "",
            "## Severity Distribution",
        ]
        for severity, count in report["severityDistribution"].items():
            lines.append(f"- {severity}: {count}")
        lines.extend(["", "## Type Distribution"])
        for event_type, count in report["typeDistribution"].items():
            lines.append(f"- {event_type}: {count}")
        lines.extend(["", "## Top Cameras"])
        for camera in report["topCameras"]:
            lines.append(f"- {camera['cameraId']}: {camera['count']}")
        lines.extend(["", "## Recommendations"])
        for recommendation in report["recommendations"]:
            lines.append(f"- {recommendation}")
        return "\n".join(lines)


report_generator = ReportGenerator()


def generate_daily_report(target_date=None):
    return report_generator.generate_daily_report(target_date)
