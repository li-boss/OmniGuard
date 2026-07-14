"""
钉钉告警服务模块
支持告警事件发送、责任人@、逐级上报
"""
import hmac
import hashlib
import base64
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class DingTalkConfig:
    """钉钉配置"""
    # Webhook URL
    WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=4c5a4520168a7ec6b34677d9c13fe52ace88eaf9e65803acf4f41b2ffed34a29"
    
    # 加签密钥
    SECRET = "SEC10c932032ac808fc939c686d758584c207dab3ead321541cca12033837d67048"
    
    # 告警级别配置
    ALERT_LEVELS = {
        "critical": {
            "priority": 1,
            "name": "严重告警",
            "color": "红色",
            "timeout": 30  # 30秒未响应则再次提醒
        },
        "high": {
            "priority": 2,
            "name": "高优先级",
            "color": "橙色",
            "timeout": 30
        },
        "medium": {
            "priority": 3,
            "name": "中优先级",
            "color": "黄色",
            "timeout": 30
        },
        "low": {
            "priority": 4,
            "name": "低优先级",
            "color": "蓝色",
            "timeout": 30
        }
    }
    
    # 责任人映射（用户ID -> 钉钉手机号）
    RESPONSIBLE_PERSONS = {
        "wang_shihan": {
            "phone": "13126557771",
            "name": "汪士涵",
            "level": 2
        },
        "wang_jinghang": {
            "phone": "13132005019",
            "name": "王靖杭",
            "level": 2
        },
        "min_shiyu": {
            "phone": "15946220502",
            "name": "闵世宇",
            "level": 2
        },
        "gao_xing": {
            "phone": "18519279527",
            "name": "高兴",
            "level": 1  # 上级领导
        }
    }
    
    # 上级领导映射（用户ID -> 上级用户ID）
    LEADER_MAPPING = {
        "wang_shihan": "gao_xing",  # 汪士涵的上级是高兴
        "wang_jinghang": "gao_xing",  # 王靖杭的上级是高兴
        "min_shiyu": "gao_xing",  # 闵世宇的上级是高兴
    }
    
    # 告警类型与责任人映射
    ALERT_TYPE_PERSON_MAPPING = {
        "围栏入侵告警": "wang_shihan",
        "陌生人告警": "wang_jinghang",
        "异常活动告警": "min_shiyu",

        "测试告警": "gao_xing",
    }
    
    # 最大上报次数
    MAX_ESCALATION_COUNT = 2



class DingTalkAlertService:
    """钉钉告警服务"""
    
    def __init__(self):
        from config import Config
        self.webhook_url = getattr(Config, 'DINGTALK_WEBHOOK', None) or DingTalkConfig.WEBHOOK_URL
        self.secret = DingTalkConfig.SECRET
        self.pending_alerts = {}  # 待响应的告警
        self._lock = threading.Lock()
        self._monitor_thread = None
        self._running = False
        
    def _generate_sign(self, timestamp: str) -> str:
        """生成加签"""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign
    
    def _get_webhook_with_sign(self) -> str:
        """获取带签名的webhook URL"""
        timestamp = str(int(time.time() * 1000))
        sign = self._generate_sign(timestamp)
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
    
    def _send_message(self, message: Dict) -> bool:
        """发送钉钉消息"""
        try:
            webhook = self._get_webhook_with_sign()
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                webhook,
                headers=headers,
                data=json.dumps(message),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info("钉钉消息发送成功")
                    return True
                else:
                    logger.error(f"钉钉消息发送失败: {result.get('errmsg')}")
                    return False
            else:
                logger.error(f"钉钉消息发送失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"发送钉钉消息异常: {e}")
            return False
    
    def send_alert(
        self,
        alert_id: str,
        alert_level: str,
        alert_type: str,
        alert_message: str,
        responsible_person_id: Optional[str] = None,
        extra_info: Optional[Dict] = None
    ) -> bool:
        """
        发送告警消息
        
        Args:
            alert_id: 告警ID
            alert_level: 告警级别
            alert_type: 告警类型（如：围栏入侵告警、陌生人告警、异常活动告警、测试告警）
            alert_message: 告警消息
            responsible_person_id: 责任人ID（可选，如果不提供则根据告警类型自动选择）
            extra_info: 额外信息
        
        Returns:
            是否发送成功
        """
        # 根据告警类型自动选择责任人
        if not responsible_person_id:
            responsible_person_id = DingTalkConfig.ALERT_TYPE_PERSON_MAPPING.get(alert_type)
            if not responsible_person_id:
                logger.error(f"未知的告警类型: {alert_type}")
                return False
        
        # 获取告警级别配置
        level_config = DingTalkConfig.ALERT_LEVELS.get(alert_level)
        if not level_config:
            logger.error(f"未知的告警级别: {alert_level}")
            return False
        
        # 获取责任人信息
        person_info = DingTalkConfig.RESPONSIBLE_PERSONS.get(responsible_person_id)
        if not person_info:
            logger.error(f"未知的责任人: {responsible_person_id}")
            return False
        
        # 构建消息内容
        title = f"【{level_config['name']}】{alert_type}"
        
        content_lines = [
            f"### {title}",
            f"",
            f"**告警级别：** {level_config['name']}",
            f"",
            f"**告警类型：** {alert_type}",
            f"",
            f"**告警时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"**告警详情：** {alert_message}",
        ]
        
        if extra_info:
            for key, value in extra_info.items():
                content_lines.append(f"")
                content_lines.append(f"**{key}：** {value}")
        
        content_lines.append(f"")
        content_lines.append(f"")
        content_lines.append(f"**责任人：** @{person_info['name']}")
        
        # 构建钉钉消息
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": "\n".join(content_lines)
            },
            "at": {
                "atMobiles": [person_info['phone']],
                "isAtAll": False
            }
        }
        
        # 发送消息
        success = self._send_message(message)
        
        if success:
            # 记录待响应告警
            with self._lock:
                self.pending_alerts[alert_id] = {
                    'alert_level': alert_level,
                    'alert_type': alert_type,
                    'alert_message': alert_message,
                    'responsible_person_id': responsible_person_id,
                    'send_time': time.time(),
                    'timeout': level_config['timeout'],
                    'escalation_count': 0
                }
        
        return success
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        确认告警（责任人响应）
        
        Args:
            alert_id: 告警ID
        
        Returns:
            是否确认成功
        """
        with self._lock:
            if alert_id in self.pending_alerts:
                del self.pending_alerts[alert_id]
                logger.info(f"告警 {alert_id} 已确认")
                return True
            return False
    
    def _escalate_alert(self, alert_id: str, alert_info: Dict) -> bool:
        """
        再次提醒责任人（30秒未响应）
        同时@上级领导
        
        Args:
            alert_id: 告警ID
            alert_info: 告警信息
        
        Returns:
            是否提醒成功
        """
        current_person_id = alert_info['responsible_person_id']
        person_info = DingTalkConfig.RESPONSIBLE_PERSONS.get(current_person_id)
        
        if not person_info:
            logger.error(f"未知的责任人: {current_person_id}")
            return False
        
        # 获取上级领导信息
        leader_id = DingTalkConfig.LEADER_MAPPING.get(current_person_id)
        leader_info = None
        if leader_id:
            leader_info = DingTalkConfig.RESPONSIBLE_PERSONS.get(leader_id)
        
        # 构建提醒消息
        title = f"【再次提醒】{alert_info['alert_type']}"
        
        content_lines = [
            f"### {title}",
            f"",
            f"⚠️ **责任人未响应，请尽快处理**",
            f"",
            f"**告警级别：** {DingTalkConfig.ALERT_LEVELS[alert_info['alert_level']]['name']}",
            f"",
            f"**告警类型：** {alert_info['alert_type']}",
            f"",
            f"**告警时间：** {datetime.fromtimestamp(alert_info['send_time']).strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"**告警详情：** {alert_info['alert_message']}",
            f"",
            f"",
            f"**责任人：** @{person_info['name']}",
        ]
        
        # 如果有上级领导，添加上级领导
        at_mobiles = [person_info['phone']]
        if leader_info:
            content_lines.append(f"")
            content_lines.append(f"**上级领导：** @{leader_info['name']}")
            at_mobiles.append(leader_info['phone'])
        
        content_lines.append(f"")
        content_lines.append(f"")
        content_lines.append(f"💡 请登录系统确认处理")
        
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": "\n".join(content_lines)
            },
            "at": {
                "atMobiles": at_mobiles,
                "isAtAll": False
            }
        }
        
        # 发送提醒消息
        success = self._send_message(message)
        
        if success:
            # 更新告警信息
            with self._lock:
                if alert_id in self.pending_alerts:
                    self.pending_alerts[alert_id]['send_time'] = time.time()
                    self.pending_alerts[alert_id]['escalation_count'] += 1
        
        return success
    
    def _monitor_alerts(self):
        """监控待响应告警（后台线程）"""
        while self._running:
            try:
                current_time = time.time()
                
                with self._lock:
                    alerts_to_escalate = []
                    
                    for alert_id, alert_info in self.pending_alerts.items():
                        elapsed_time = current_time - alert_info['send_time']
                        
                        if elapsed_time > alert_info['timeout']:
                            if alert_info['escalation_count'] < DingTalkConfig.MAX_ESCALATION_COUNT:
                                alerts_to_escalate.append((alert_id, alert_info))
                            else:
                                del self.pending_alerts[alert_id]
                                logger.info(f"告警 {alert_id} 已达到最大上报次数，停止监控")
                
                # 再次提醒
                for alert_id, alert_info in alerts_to_escalate:
                    self._escalate_alert(alert_id, alert_info)
                
                time.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                logger.error(f"告警监控异常: {e}")
                time.sleep(10)
    
    def start(self):
        """启动告警服务"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_alerts,
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("钉钉告警服务已启动")
    
    def stop(self):
        """停止告警服务"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("钉钉告警服务已停止")


# 全局单例
_alert_service = None


def get_alert_service() -> DingTalkAlertService:
    """获取告警服务实例"""
    global _alert_service
    if _alert_service is None:
        _alert_service = DingTalkAlertService()
    return _alert_service


# ==================== 异常活动告警功能说明 ====================
# 
# 异常活动告警功能待开发，以下是需要实现的功能点：
#
# 1. 触发条件（待定义）：
#    - 人员在非工作时间进入敏感区域
#    - 人员行为异常（如奔跑、徘徊、跌倒等）
#    - 人员聚集超过阈值
#    - 其他异常行为模式
#
# 2. 调用方式：
#    alert_service.send_alert(
#        alert_id="abnormal_activity_xxx",
#        alert_level="medium",
#        alert_type="异常活动告警",
#        alert_message="检测到异常活动：xxx",
#        # responsible_person_id 可选，会自动选择 "min_shiyu"
#    )
#
# 3. 责任人：闵世宇 (15946220502)
#
# 4. 实现步骤：
#    a. 在 backend/core_cv/pipeline.py 中添加异常活动检测逻辑
#    b. 在 backend/services/alert_handler.py 中添加 handle_abnormal_activity_alert 方法
#    c. 在 backend/core_cv/rule_engine.py 中添加异常活动规则评估
#    d. 在前端添加异常活动告警的展示和处理
#
# 5. 数据库字段：
#    - 可以在 AlarmEvent 模型中使用现有的 alarm_type 字段
#    - 值为 "abnormal_activity" 或 "异常活动"
#
# ==================== 异常活动告警功能说明结束 ====================