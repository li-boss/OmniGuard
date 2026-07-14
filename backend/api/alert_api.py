"""
告警API接口
提供告警发送、确认、查询等功能
"""
from flask import Blueprint, request, jsonify
from services.alert_handler import get_alert_handler
import logging

logger = logging.getLogger(__name__)

alert_bp = Blueprint('alert', __name__, url_prefix='/api/alerts')


@alert_bp.route('/send', methods=['POST'])
def send_alert():
    """
    发送告警
    
    Request Body:
    {
        "alert_level": "high",
        "alert_type": "围栏入侵",
        "alert_message": "人员在禁区内停留超过2分钟",
        "responsible_person_id": "user_001",
        "extra_info": {}
    }
    """
    try:
        data = request.get_json()
        
        alert_level = data.get('alert_level')
        alert_type = data.get('alert_type')
        alert_message = data.get('alert_message')
        responsible_person_id = data.get('responsible_person_id')
        extra_info = data.get('extra_info', {})
        
        if not all([alert_level, alert_type, alert_message, responsible_person_id]):
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        # 生成告警ID
        from datetime import datetime
        alert_id = f"manual_{int(datetime.now().timestamp())}"
        
        # 发送告警
        alert_handler = get_alert_handler()
        success = alert_handler.alert_service.send_alert(
            alert_id=alert_id,
            alert_level=alert_level,
            alert_type=alert_type,
            alert_message=alert_message,
            responsible_person_id=responsible_person_id,
            extra_info=extra_info
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '告警发送成功',
                'alert_id': alert_id
            })
        else:
            return jsonify({
                'success': False,
                'message': '告警发送失败'
            }), 500
            
    except Exception as e:
        logger.error(f"发送告警失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@alert_bp.route('/acknowledge', methods=['POST'])
def acknowledge_alert():
    """
    确认告警
    
    Request Body:
    {
        "alert_id": "zone_1_123_1234567890"
    }
    """
    try:
        data = request.get_json()
        alert_id = data.get('alert_id')
        
        if not alert_id:
            return jsonify({
                'success': False,
                'message': '缺少告警ID'
            }), 400
        
        alert_handler = get_alert_handler()
        success = alert_handler.acknowledge_alert(alert_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '告警已确认'
            })
        else:
            return jsonify({
                'success': False,
                'message': '告警不存在或已确认'
            }), 404
            
    except Exception as e:
        logger.error(f"确认告警失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@alert_bp.route('/pending', methods=['GET'])
def get_pending_alerts():
    """
    获取待响应告警列表
    """
    try:
        alert_handler = get_alert_handler()
        
        with alert_handler.alert_service._lock:
            alerts = []
            for alert_id, alert_info in alert_handler.alert_service.pending_alerts.items():
                alerts.append({
                    'alert_id': alert_id,
                    'alert_level': alert_info['alert_level'],
                    'alert_type': alert_info['alert_type'],
                    'alert_message': alert_info['alert_message'],
                    'responsible_person_id': alert_info['responsible_person_id'],
                    'send_time': alert_info['send_time'],
                    'escalation_count': alert_info['escalation_count']
                })
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts)
        })
        
    except Exception as e:
        logger.error(f"获取待响应告警失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@alert_bp.route('/test', methods=['POST'])
def test_alert():
    """
    测试钉钉告警
    
    Request Body:
    {
        "responsible_person_id": "user_001"
    }
    """
    try:
        data = request.get_json()
        responsible_person_id = data.get('responsible_person_id')
        
        if not responsible_person_id:
            return jsonify({
                'success': False,
                'message': '缺少责任人ID'
            }), 400
        
        alert_handler = get_alert_handler()
        
        from datetime import datetime
        alert_id = f"test_{int(datetime.now().timestamp())}"
        
        success = alert_handler.alert_service.send_alert(
            alert_id=alert_id,
            alert_level="medium",
            alert_type="测试告警",
            alert_message="这是一条测试告警消息",
            responsible_person_id=responsible_person_id,
            extra_info={"测试时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '测试告警发送成功，请检查钉钉群'
            })
        else:
            return jsonify({
                'success': False,
                'message': '测试告警发送失败，请检查配置'
            }), 500
            
    except Exception as e:
        logger.error(f"测试告警失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500