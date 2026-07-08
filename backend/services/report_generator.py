import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from models import db
from models.alarm import AlarmEvent

logger = logging.getLogger(__name__)


class ReportGenerator:

    def generate_daily_report(self, target_date=None):
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()
        elif isinstance(target_date, str):
            target_date = datetime.fromisoformat(target_date).date()

        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        total = AlarmEvent.query.filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
        ).count()

        resolved = AlarmEvent.query.filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
            AlarmEvent.status == 'resolved',
        ).count()

        false_positive = AlarmEvent.query.filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
            AlarmEvent.status == 'false_positive',
        ).count()

        pending = AlarmEvent.query.filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
            AlarmEvent.status.in_(['pending', 'handling']),
        ).count()

        severity_stats = db.session.query(
            AlarmEvent.severity, func.count(AlarmEvent.id)
        ).filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
        ).group_by(AlarmEvent.severity).all()

        type_stats = db.session.query(
            AlarmEvent.alarm_type, func.count(AlarmEvent.id)
        ).filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
        ).group_by(AlarmEvent.alarm_type).all()

        camera_stats = db.session.query(
            AlarmEvent.camera_id, func.count(AlarmEvent.id)
        ).filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
        ).group_by(AlarmEvent.camera_id).order_by(func.count(AlarmEvent.id).desc()).limit(5).all()

        avg_handle_time = None
        handled_alarms = AlarmEvent.query.filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
            AlarmEvent.handle_time != None,
        ).all()
        if handled_alarms:
            total_seconds = sum(
                (a.handle_time - a.created_at).total_seconds() for a in handled_alarms
            )
            avg_handle_time = round(total_seconds / len(handled_alarms), 1)

        resolve_rate = round(resolved / total * 100, 1) if total > 0 else 0.0

        report = {
            'report_date': target_date.isoformat(),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_alarms': total,
                'resolved': resolved,
                'false_positive': false_positive,
                'pending': pending,
                'resolve_rate': resolve_rate,
                'avg_handle_time_seconds': avg_handle_time,
            },
            'severity_distribution': {s: c for s, c in severity_stats},
            'type_distribution': {t: c for t, c in type_stats},
            'top_cameras': [{'camera_id': c, 'count': cnt} for c, cnt in camera_stats],
            'recommendations': self._generate_recommendations(total, resolve_rate, avg_handle_time, severity_stats),
        }

        logger.info('Daily report generated for %s', target_date)
        return report

    def _generate_recommendations(self, total, resolve_rate, avg_handle_time, severity_stats):
        recommendations = []
        if resolve_rate < 80:
            recommendations.append('告警处置率低于80%，建议增加值班人员或优化处置流程')
        if avg_handle_time and avg_handle_time > 600:
            recommendations.append('平均处置时间超过10分钟，建议检查告警通知是否及时送达')
        for severity, count in severity_stats:
            if severity == 'critical' and count > 3:
                recommendations.append(f'今日严重告警{count}条，建议重点排查相关区域')
        if not recommendations:
            recommendations.append('系统运行正常，继续保持')
        return recommendations

    def format_report_markdown(self, report):
        lines = [
            f'# 智慧校园安防日报 - {report["report_date"]}',
            '',
            '## 概览',
            f'- 总告警数: {report["summary"]["total_alarms"]}',
            f'- 已处置: {report["summary"]["resolved"]}',
            f'- 误报: {report["summary"]["false_positive"]}',
            f'- 待处理: {report["summary"]["pending"]}',
            f'- 处置率: {report["summary"]["resolve_rate"]}%',
            f'- 平均处置时间: {report["summary"]["avg_handle_time_seconds"]}秒',
            '',
            '## 严重级别分布',
        ]
        for severity, count in report['severity_distribution'].items():
            lines.append(f'- {severity}: {count}')
        lines.append('')
        lines.append('## 告警类型分布')
        for atype, count in report['type_distribution'].items():
            lines.append(f'- {atype}: {count}')
        lines.append('')
        lines.append('## 高频摄像头 TOP5')
        for cam in report['top_cameras']:
            lines.append(f'- {cam["camera_id"]}: {cam["count"]}次')
        lines.append('')
        lines.append('## 建议')
        for rec in report['recommendations']:
            lines.append(f'- {rec}')
        return '\n'.join(lines)


report_generator = ReportGenerator()
