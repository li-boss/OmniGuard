import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class DailyReportService:
    def __init__(self, app=None):
        self.app = app
        self.reports_dir = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
        self.reports_dir = Path(app.root_path) / 'static' / 'reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DailyReportService initialized, reports dir: {self.reports_dir}")
    
    def generate_report(self, start_time=None, end_time=None):
        """
        生成日报
        :param start_time: 开始时间，默认为24小时前
        :param end_time: 结束时间，默认为当前时间
        :return: 日报数据
        """
        from models import db, AlarmEvent, DailyReport
        
        logger.info(f"Starting generate_report, reports_dir: {self.reports_dir}")
        
        if self.reports_dir is None:
            raise ValueError("reports_dir is not initialized. Please call init_app() first.")
        
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(hours=24)
        
        logger.info(f"Generating daily report from {start_time} to {end_time}")
        
        alarms = AlarmEvent.query.filter(
            AlarmEvent.created_at >= start_time,
            AlarmEvent.created_at <= end_time
        ).order_by(AlarmEvent.created_at.desc()).all()
        
        logger.info(f"Found {len(alarms)} alarms in time range")
        if alarms:
            alarm_types = {}
            for a in alarms:
                t = self._get_detailed_alarm_type(a)
                alarm_types[t] = alarm_types.get(t, 0) + 1
            logger.info(f"Alarm types distribution (detailed): {alarm_types}")
        
        alarm_stats = self._analyze_alarms(alarms)
        logger.info(f"Alarm stats: {alarm_stats}")
        
        risk_score = DailyReport.calculate_risk_score(
            alarm_stats['critical_count'],
            alarm_stats['high_count'],
            alarm_stats['medium_count'],
            alarm_stats['low_count']
        )
        risk_level = DailyReport.get_risk_level(risk_score)
        
        summary = self._generate_summary(alarm_stats, risk_score, risk_level)
        
        ai_analysis = self._generate_ai_analysis(alarm_stats, alarms)
        
        alarm_list = []
        for alarm in alarms:
            alarm_dict = alarm.to_dict()
            alarm_dict['type'] = self._get_detailed_alarm_type(alarm)
            alarm_list.append(alarm_dict)
        
        report_data = {
            'title': '校园安全日报',
            'generated_at': end_time.isoformat(),
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': 24
            },
            'summary': summary,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'statistics': alarm_stats,
            'alarms': alarm_list,
            'analysis': ai_analysis['analysis'],
            'suggestions': ai_analysis['suggestions']
        }
        
        timestamp_str = end_time.strftime("%Y%m%d_%H%M%S")
        json_filename = f"report_{timestamp_str}.json"
        pdf_filename = f"report_{timestamp_str}.pdf"
        
        json_path = self._save_json(report_data, json_filename)
        pdf_path = self._generate_pdf(report_data, pdf_filename)
        
        report_record = DailyReport(
            title='校园安全日报',
            generated_at=end_time,
            summary=summary,
            risk_score=risk_score,
            risk_level=risk_level,
            start_time=start_time,
            end_time=end_time,
            total_alarms=len(alarms),
            critical_alarms=alarm_stats['critical_count'],
            high_alarms=alarm_stats['high_count'],
            medium_alarms=alarm_stats['medium_count'],
            low_alarms=alarm_stats['low_count'],
            json_path=json_path,
            pdf_path=pdf_path
        )
        
        db.session.add(report_record)
        db.session.commit()
        
        logger.info(f"Daily report generated successfully, ID: {report_record.id}")
        
        return report_record.to_dict()
    
    def _get_detailed_alarm_type(self, alarm):
        """获取详细的告警类型"""
        alarm_type_map = {
            "electronic_fence": "围栏入侵告警",
            "stranger": "陌生人告警",
            "intrusion": "围栏入侵告警",
            "围栏入侵告警": "围栏入侵告警",
            "陌生人告警": "陌生人告警",
        }
        
        raw_type = alarm.alarm_type or '未知'
        description = alarm.description or ''
        
        if raw_type in ('fall', 'fire', '异常活动告警'):
            if '跌倒' in description or raw_type == 'fall':
                return "异常活动告警——跌倒"
            elif '火情' in description or raw_type == 'fire':
                return "异常活动告警——火情"
            else:
                return "异常活动告警"
        
        return alarm_type_map.get(raw_type, raw_type)
    
    def _analyze_alarms(self, alarms):
        """分析告警事件"""
        stats = {
            'total': len(alarms),
            'by_type': {},
            'by_severity': {
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0
            },
            'critical_count': 0,
            'high_count': 0,
            'medium_count': 0,
            'low_count': 0
        }
        
        for alarm in alarms:
            alarm_type = self._get_detailed_alarm_type(alarm)
            stats['by_type'][alarm_type] = stats['by_type'].get(alarm_type, 0) + 1
            
            severity = alarm.severity or 'medium'
            stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1
            
            if severity == 'critical':
                stats['critical_count'] += 1
            elif severity == 'high':
                stats['high_count'] += 1
            elif severity == 'medium':
                stats['medium_count'] += 1
            else:
                stats['low_count'] += 1
        
        return stats
    
    def _generate_summary(self, stats, risk_score, risk_level):
        """生成一句话概括"""
        total = stats['total']
        if total == 0:
            return f"过去24小时内未发生安全告警事件，校园安全状况良好，风险等级：{risk_level}"
        
        main_types = sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True)[:2]
        types_str = '、'.join([t[0] for t in main_types])
        
        return f"过去24小时内共发生{total}次安全告警，主要类型为{types_str}，风险评分{risk_score}分，风险等级：{risk_level}"
    
    def _generate_ai_analysis(self, stats, alarms):
        """生成 AI 分析和建议"""
        try:
            from services.ai_analyzer import AIAnalyzer
            analyzer = AIAnalyzer()
            return analyzer.analyze(stats, alarms)
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}, using fallback")
            return self._generate_fallback_analysis(stats, alarms)
    
    def _generate_fallback_analysis(self, stats, alarms):
        """备用分析（当 AI 模型不可用时）"""
        analysis = []
        suggestions = []
        
        total = stats['total']
        if total == 0:
            analysis.append("过去24小时内未发生安全告警事件，校园整体安全状况良好。")
            suggestions.append("继续保持现有的安全监控措施，定期检查监控设备运行状态。")
            suggestions.append("建议定期开展安全演练，提高师生安全意识。")
        else:
            if stats['critical_count'] > 0:
                analysis.append(f"过去24小时内发生了{stats['critical_count']}次严重告警，需要重点关注和处理。")
            
            if stats['by_type']:
                sorted_types = sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True)
                main_types = sorted_types[:3]
                type_str = "、".join([f"{t[0]}({t[1]}次)" for t in main_types])
                analysis.append(f"告警类型分布：{type_str}。")
            
            if stats['by_severity']['high'] > 5:
                analysis.append("高等级告警数量较多，建议加强重点区域的监控力度。")
            
            suggestions.append("建议加强重点区域的巡逻频次，确保安全人员及时响应告警。")
            suggestions.append("定期检查和维护监控设备，确保监控系统稳定运行。")
            
            if '围栏入侵告警' in stats['by_type']:
                suggestions.append("针对围栏入侵告警，建议检查围栏完整性，必要时加固防护设施。")
            
            if '陌生人告警' in stats['by_type']:
                suggestions.append("针对陌生人告警，建议加强门禁管理，完善访客登记制度。")
            
            fall_count = sum(v for k, v in stats['by_type'].items() if '跌倒' in k)
            if fall_count > 0:
                analysis.append(f"检测到{fall_count}次跌倒告警，需关注人员安全，建议检查地面防滑措施。")
                suggestions.append("针对跌倒告警，建议检查地面湿滑情况，增设防滑设施和警示标识。")
            
            fire_count = sum(v for k, v in stats['by_type'].items() if '火情' in k)
            if fire_count > 0:
                analysis.append(f"检测到{fire_count}次火情告警，需立即排查火灾隐患。")
                suggestions.append("针对火情告警，建议检查消防设施完好性，加强火灾隐患排查。")
        
        return {'analysis': analysis, 'suggestions': suggestions}
    
    def _save_json(self, data, filename):
        """保存 JSON 文件"""
        filepath = self.reports_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Report JSON saved to {filepath}")
        return f"/static/reports/{filename}"
    
    def _generate_pdf(self, data, filename):
        """生成 PDF 文件"""
        try:
            from services.pdf_generator import PDFGenerator
            generator = PDFGenerator()
            filepath = self.reports_dir / filename
            generator.generate(data, filepath)
            logger.info(f"Report PDF saved to {filepath}")
            return f"/static/reports/{filename}"
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return None
    
    def get_report_list(self, page=1, per_page=10):
        """获取日报列表"""
        from models import DailyReport
        
        pagination = DailyReport.query.order_by(
            DailyReport.generated_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': [report.to_dict() for report in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages
        }
    
    def get_report_detail(self, report_id):
        """获取日报详情"""
        from models import DailyReport
        
        report = DailyReport.query.get(report_id)
        if not report:
            return None
        
        report_dict = report.to_dict()
        
        json_path = self.reports_dir / Path(report.json_path).name
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                report_dict['content'] = json.load(f)
        
        return report_dict
    
    def delete_report(self, report_id):
        """删除日报"""
        from models import db, DailyReport
        
        report = DailyReport.query.get(report_id)
        if not report:
            return False
        
        json_path = self.reports_dir / Path(report.json_path).name
        if json_path.exists():
            os.remove(json_path)
        
        if report.pdf_path:
            pdf_path = self.reports_dir / Path(report.pdf_path).name
            if pdf_path.exists():
                os.remove(pdf_path)
        
        db.session.delete(report)
        db.session.commit()
        
        logger.info(f"Daily report deleted, ID: {report_id}")
        return True