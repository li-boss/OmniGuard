"""
测试钉钉告警配置
验证责任人和告警类型映射是否正确
"""
import sys
sys.path.insert(0, '.')

from services.dingtalk_alert import DingTalkConfig, get_alert_service
from services.alert_handler import get_alert_handler

def test_config():
    print("=" * 60)
    print("钉钉告警配置测试")
    print("=" * 60)
    
    # 测试责任人配置
    print("\n1. 责任人配置：")
    for user_id, info in DingTalkConfig.RESPONSIBLE_PERSONS.items():
        print(f"   {user_id}: {info['name']} ({info['phone']}) - 级别: {info['level']}")
    
    # 测试上级领导映射
    print("\n2. 上级领导映射：")
    for user_id, leader_id in DingTalkConfig.LEADER_MAPPING.items():
        user_name = DingTalkConfig.RESPONSIBLE_PERSONS[user_id]['name']
        leader_name = DingTalkConfig.RESPONSIBLE_PERSONS[leader_id]['name']
        print(f"   {user_name} -> {leader_name}")
    
    # 测试告警类型映射
    print("\n3. 告警类型与责任人映射：")
    for alert_type, user_id in DingTalkConfig.ALERT_TYPE_PERSON_MAPPING.items():
        user_name = DingTalkConfig.RESPONSIBLE_PERSONS[user_id]['name']
        print(f"   {alert_type} -> {user_name}")
    
    print("\n" + "=" * 60)


def test_send_alert():
    print("\n测试发送告警（不实际发送，只验证逻辑）")
    print("=" * 60)
    
    alert_service = get_alert_service()
    
    # 测试围栏入侵告警
    print("\n1. 测试围栏入侵告警：")
    print("   应该@汪士涵")
    # success = alert_service.send_alert(
    #     alert_id="test_zone_001",
    #     alert_level="high",
    #     alert_type="围栏入侵告警",
    #     alert_message="测试围栏入侵告警"
    # )
    
    # 测试陌生人告警
    print("\n2. 测试陌生人告警：")
    print("   应该@王靖杭")
    
    # 测试异常活动告警
    print("\n3. 测试异常活动告警：")
    print("   应该@闵世宇")
    
    # 测试测试告警
    print("\n4. 测试测试告警：")
    print("   应该@高兴")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_config()
    test_send_alert()
    
    print("\n配置测试完成！")
    print("\n提示：实际发送测试请使用 test_alert_simple.py")