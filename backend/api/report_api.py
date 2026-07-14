from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

from models import DailyReport
from services.daily_report_service import DailyReportService

report_bp = Blueprint('report_api', __name__)
logger = logging.getLogger(__name__)


def get_report_service():
    logger.info(f"Creating DailyReportService with app: {current_app}")
    service = DailyReportService(current_app._get_current_object())
    logger.info(f"DailyReportService created, reports_dir: {service.reports_dir}")
    return service


@report_bp.route('/generate', methods=['POST'])
@jwt_required()
def generate_report():
    """生成日报"""
    try:
        data = request.get_json() or {}
        logger.info(f"Received generate report request")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        if data.get('start_time'):
            start_time = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            end_time = datetime.fromisoformat(data['end_time'])
        
        logger.info(f"Time range: {start_time} to {end_time}")
        report_service = get_report_service()
        report = report_service.generate_report(start_time, end_time)
        logger.info(f"Report generated successfully, id: {report.get('id')}")
        
        return jsonify({
            'code': 0,
            'message': '日报生成成功',
            'data': report
        })
    except Exception as e:
        import traceback
        logger.error(f"Failed to generate report: {e}")
        traceback.print_exc()
        return jsonify({
            'code': 500,
            'message': f'日报生成失败: {str(e)}'
        }), 500


@report_bp.route('', methods=['GET'])
@jwt_required()
def get_report_list():
    """获取日报列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        report_service = get_report_service()
        result = report_service.get_report_list(page, per_page)
        
        return jsonify({
            'code': 0,
            'message': 'ok',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取日报列表失败: {str(e)}'
        }), 500


@report_bp.route('/<int:report_id>', methods=['GET'])
@jwt_required()
def get_report_detail(report_id):
    """获取日报详情"""
    try:
        report_service = get_report_service()
        report = report_service.get_report_detail(report_id)
        
        if not report:
            return jsonify({
                'code': 404,
                'message': '日报不存在'
            }), 404
        
        return jsonify({
            'code': 0,
            'message': 'ok',
            'data': report
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取日报详情失败: {str(e)}'
        }), 500


@report_bp.route('/<int:report_id>', methods=['DELETE'])
@jwt_required()
def delete_report(report_id):
    """删除日报"""
    try:
        report_service = get_report_service()
        success = report_service.delete_report(report_id)
        
        if not success:
            return jsonify({
                'code': 404,
                'message': '日报不存在'
            }), 404
        
        return jsonify({
            'code': 0,
            'message': '日报删除成功'
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'删除日报失败: {str(e)}'
        }), 500


@report_bp.route('/<int:report_id>/download', methods=['GET'])
@jwt_required()
def download_report(report_id):
    """下载日报 PDF"""
    try:
        report = DailyReport.query.get(report_id)
        
        if not report:
            return jsonify({
                'code': 404,
                'message': '日报不存在'
            }), 404
        
        if not report.pdf_path:
            return jsonify({
                'code': 404,
                'message': 'PDF 文件不存在'
            }), 404
        
        from pathlib import Path
        from flask import current_app
        
        pdf_path = Path(current_app.root_path) / 'static' / 'reports' / Path(report.pdf_path).name
        
        if not pdf_path.exists():
            return jsonify({
                'code': 404,
                'message': 'PDF 文件不存在'
            }), 404
        
        return send_file(
            str(pdf_path),
            as_attachment=True,
            download_name=f"校园安全日报_{report.generated_at.strftime('%Y%m%d')}.pdf"
        )
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'下载日报失败: {str(e)}'
        }), 500