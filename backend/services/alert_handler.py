"""
告警事件处理器
集成钉钉告警服务
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from .dingtalk_alert import get_alert_service, DingTalkConfig

logger = logging.getLogger(__name__)


class AlertEventHandler:
    """告警事件处理器"""
    
    def __init__(self):
        self.alert_service = get_alert_service()
    
    def handle_zone_alert(
        self,
        zone_id: int,
        zone_name: str,
        object_id: int,
        duration: float,
        camera_id: str = "cam-1",
        alert_id: Optional[str] = None
    ) -> bool:
        """
        处理围栏告警
        
        Args:
            zone_id: 围栏ID
            zone_name: 围栏名称
            object_id: 对象ID
            duration: 停留时长（秒）
            camera_id: 摄像头ID
            alert_id: 告警ID（可选，如果不提供则自动生成）
        
        Returns:
            是否处理成功
        """
        try:
            # 生成告警ID（如果未提供）
            if not alert_id:
                alert_id = f"zone_{zone_id}_{object_id}_{int(datetime.now().timestamp())}"
            
            # 判断告警级别
            if duration > 300:  # 超过5分钟
                alert_level = "critical"
            elif duration > 180:  # 超过3分钟
                alert_level = "high"
            elif duration > 60:  # 超过1分钟
                alert_level = "medium"
            else:
                alert_level = "low"
            
            # 获取责任人（根据告警类型自动选择）
            # 围栏入侵告警 -> 汪士涵
            # 不再需要手动指定，由 dingtalk_alert.py 根据告警类型自动选择
            
            # 构建告警消息
            alert_message = f"人员(ID:{object_id})在围栏【{zone_name}】内停留{duration:.1f}秒"
            
            # 额外信息
            extra_info = {
                "围栏ID": zone_id,
                "对象ID": object_id,
                "摄像头": camera_id
            }
            
            # 发送钉钉告警（不传 responsible_person_id，自动选择）
            return self.alert_service.send_alert(
                alert_id=alert_id,
                alert_level=alert_level,
                alert_type="围栏入侵告警",
                alert_message=alert_message,
                extra_info=extra_info
            )
            
        except Exception as e:
            logger.error(f"处理围栏告警失败: {e}")
            return False
    
    def handle_face_alert(
        self,
        user_name: str,
        confidence: float,
        camera_id: str = "cam-1"
    ) -> bool:
        """
        处理人脸识别告警（陌生人告警）
        
        Args:
            user_name: 用户名称
            confidence: 置信度
            camera_id: 摄像头ID
        
        Returns:
            是否处理成功
        """
        try:
            # 生成告警ID
            alert_id = f"face_{int(datetime.now().timestamp())}"
            
            # 陌生人告警默认为中等优先级
            alert_level = "medium"
            
            # 构建告警消息
            alert_message = f"检测到陌生人：{user_name}（置信度：{confidence:.2f}）"
            
            # 额外信息
            extra_info = {
                "用户名称": user_name,
                "置信度": f"{confidence:.2f}",
                "摄像头": camera_id
            }
            
            # 发送钉钉告警（不传 responsible_person_id，自动选择）
            return self.alert_service.send_alert(
                alert_id=alert_id,
                alert_level=alert_level,
                alert_type="陌生人告警",
                alert_message=alert_message,
                extra_info=extra_info
            )
            
        except Exception as e:
            logger.error(f"处理人脸告警失败: {e}")
            return False
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        确认告警
        
        Args:
            alert_id: 告警ID
        
        Returns:
            是否确认成功
        """
        return self.alert_service.acknowledge_alert(alert_id)
    

    def start(self):
        """启动告警处理器"""
        self.alert_service.start()
    
    def stop(self):
        """停止告警处理器"""
        self.alert_service.stop()


# 全局单例
_alert_handler = None


def get_alert_handler() -> AlertEventHandler:
    """获取告警处理器实例"""
    global _alert_handler
    if _alert_handler is None:
        _alert_handler = AlertEventHandler()
    return _alert_handler