import logging
import os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not installed. PDF generation will be disabled.")


def get_chinese_font():
    font_paths = [
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simsun.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/PingFang.ttc',
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            return font_path
    
    return None


class PDFGenerator:
    def __init__(self):
        self.styles = None
        self.font_name = 'Helvetica'
        if REPORTLAB_AVAILABLE:
            self._init_chinese_font()
            self._init_styles()
    
    def _init_chinese_font(self):
        font_path = get_chinese_font()
        if font_path:
            try:
                font_name = 'ChineseFont'
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                self.font_name = font_name
                logger.info(f"Chinese font registered: {font_path}")
            except Exception as e:
                logger.warning(f"Failed to register Chinese font: {e}")
        else:
            logger.warning("No Chinese font found, PDF may not display Chinese correctly")
    
    def _init_styles(self):
        """初始化样式"""
        self.styles = getSampleStyleSheet()
        
        self.styles.add(ParagraphStyle(
            name='ChineseTitle',
            fontName=self.font_name,
            fontSize=18,
            leading=22,
            alignment=1,
            spaceAfter=20
        ))
        
        self.styles.add(ParagraphStyle(
            name='ChineseHeading',
            fontName=self.font_name,
            fontSize=14,
            leading=18,
            spaceBefore=15,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='ChineseBody',
            fontName=self.font_name,
            fontSize=11,
            leading=16,
            spaceBefore=6,
            spaceAfter=6
        ))
    
    def generate(self, data, filepath):
        """生成 PDF 文件"""
        if not REPORTLAB_AVAILABLE:
            logger.error("ReportLab not available, cannot generate PDF")
            return False
        
        try:
            doc = SimpleDocTemplate(
                str(filepath),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            story = []
            
            story.append(Paragraph(
                f"<b>{data['title']}</b>",
                self.styles['ChineseTitle']
            ))
            
            generated_at = datetime.fromisoformat(data['generated_at']).strftime('%Y-%m-%d %H:%M:%S')
            story.append(Paragraph(
                f"生成时间：{generated_at}",
                self.styles['ChineseBody']
            ))
            story.append(Spacer(1, 20))
            
            story.append(Paragraph("<b>一、监控概况</b>", self.styles['ChineseHeading']))
            
            period = data['period']
            start_time = datetime.fromisoformat(period['start']).strftime('%Y-%m-%d %H:%M:%S')
            end_time = datetime.fromisoformat(period['end']).strftime('%Y-%m-%d %H:%M:%S')
            
            overview_data = [
                ['监控时长', f"{period['hours']} 小时"],
                ['告警总数', f"{data['statistics']['total']} 次"],
                ['风险评分', f"{data['risk_score']} 分"],
                ['风险等级', data['risk_level']],
                ['监控时段', f"{start_time} 至 {end_time}"]
            ]
            
            overview_table = Table(overview_data, colWidths=[3*cm, 10*cm])
            overview_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            story.append(overview_table)
            story.append(Spacer(1, 20))
            
            story.append(Paragraph("<b>二、告警事件统计</b>", self.styles['ChineseHeading']))
            
            stats = data['statistics']
            
            story.append(Paragraph("<b>1. 按类型统计：</b>", self.styles['ChineseBody']))
            type_data = [['告警类型', '次数']]
            for alarm_type, count in stats['by_type'].items():
                type_data.append([alarm_type, f"{count} 次"])
            
            type_table = Table(type_data, colWidths=[6*cm, 4*cm])
            type_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ]))
            story.append(type_table)
            story.append(Spacer(1, 10))
            
            story.append(Paragraph("<b>2. 按严重程度统计：</b>", self.styles['ChineseBody']))
            severity_data = [
                ['严重程度', '次数'],
                ['严重', f"{stats['by_severity']['critical']} 次"],
                ['高', f"{stats['by_severity']['high']} 次"],
                ['中', f"{stats['by_severity']['medium']} 次"],
                ['低', f"{stats['by_severity']['low']} 次"]
            ]
            
            severity_table = Table(severity_data, colWidths=[6*cm, 4*cm])
            severity_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ]))
            story.append(severity_table)
            story.append(Spacer(1, 20))
            
            if data['alarms']:
                story.append(Paragraph("<b>三、详细告警列表</b>", self.styles['ChineseHeading']))
                
                alarm_data = [['时间', '类型', '摄像头', '严重程度']]
                for alarm in data['alarms'][:20]:
                    alarm_time = datetime.fromisoformat(alarm['created_at'].replace('Z', '')).strftime('%m-%d %H:%M')
                    alarm_data.append([
                        alarm_time,
                        alarm.get('type', '未知')[:15],
                        alarm.get('camera_id', '未知'),
                        alarm.get('severity', '中')
                    ])
                
                alarm_table = Table(alarm_data, colWidths=[2.5*cm, 4*cm, 3*cm, 3*cm])
                alarm_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                story.append(alarm_table)
                story.append(Spacer(1, 20))
            
            story.append(Paragraph("<b>四、安全分析</b>", self.styles['ChineseHeading']))
            for i, analysis in enumerate(data['analysis'], 1):
                story.append(Paragraph(f"{i}. {analysis}", self.styles['ChineseBody']))
            story.append(Spacer(1, 20))
            
            story.append(Paragraph("<b>五、改进建议</b>", self.styles['ChineseHeading']))
            for i, suggestion in enumerate(data['suggestions'], 1):
                story.append(Paragraph(f"{i}. {suggestion}", self.styles['ChineseBody']))
            
            doc.build(story)
            logger.info(f"PDF generated successfully: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return False