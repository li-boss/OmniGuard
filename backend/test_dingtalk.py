"""
钉钉告警测试脚本
用于测试钉钉配置是否正确
"""
import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.dingtalk_alert import get_alert_service, DingTalkConfig


def test_config():
    """测试配置是否正确"""
    print("=" * 60)
    print("钉钉告警配置检查")
    print("=" * 60)
    
    # 检查Webhook URL
    if DingTalkConfig.WEBHOOK_URL == "https://oapi.dingtalk.com/robot/send?access_token=YOUR_ACCESS_TOKEN":
        print("❌ Webhook URL 未配置")
        print("   请在 backend/services/dingtalk_alert.py 中配置 WEBHOOK_URL")
        return False
    else:
        print(f"✅ Webhook URL: {DingTalkConfig.WEBHOOK_URL[:50]}...")
    
    # 检查密钥
    if DingTalkConfig.SECRET == "YOUR_SECRET":
        print("❌ 加签密钥未配置")
        print("   请在 backend/services/dingtalk_alert.py 中配置 SECRET")
        return False
    else:
        print(f"✅ 加签密钥: {DingTalkConfig.SECRET[:10]}...")
    
    # 检查责任人
    if not DingTalkConfig.RESPONSIBLE_PERSONS:
        print("❌ 未配置责任人")
        print("   请在 backend/services/dingtalk_alert.py 中配置 RESPONSIBLE_PERSONS")
        return False
    else:
        print(f"✅ 责任人数量: {len(DingTalkConfig.RESPONSIBLE_PERSONS)}")
        for user_id, info in DingTalkConfig.RESPONSIBLE_PERSONS.items():
            print(f"   - {user_id}: {info['name']} ({info['phone']})")
    
    print("\n配置检查通过！")
    return True


def test_send_alert():
    """测试发送告警"""
    print("\n" + "=" * 60)
    print("测试发送钉钉告警")
    print("=" * 60)
    
    if not DingTalkConfig.RESPONSIBLE_PERSONS:
        print("❌ 未配置责任人，无法测试")
        return False
    
    # 获取第一个责任人
    user_id = list(DingTalkConfig.RESPONSIBLE_PERSONS.keys())[0]
    user_info = DingTalkConfig.RESPONSIBLE_PERSONS[user_id]
    
    print(f"发送测试告警给: {user_info['name']} ({user_info['phone']})")
    
    alert_service = get_alert_service()
    
    from datetime import datetime
    alert_id = f"test_{int(datetime.now().timestamp())}"
    
    success = alert_service.send_alert(
        alert_id=alert_id,
        alert_level="medium",
        alert_type="测试告警",
        alert_message="这是一条测试告警消息，用于验证钉钉配置是否正确",
        responsible_person_id=user_id,
        extra_info={
            "测试时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "测试人员": "系统管理员"
        }
    )
    
    if success:
        print("\n✅ 告警发送成功！")
        print("   请检查钉钉群是否收到消息")
        print(f"   告警ID: {alert_id}")
        return True
    else:
        print("\n❌ 告警发送失败！")
        print("   请检查：")
        print("   1. Webhook URL 是否正确")
        print("   2. 加签密钥是否正确")
        print("   3. 责任人手机号是否与钉钉绑定手机号一致")
        print("   4. 网络是否能访问钉钉API")
        return False


def test_escalation():
    """测试逐级上报"""
    print("\n" + "=" * 60)
    print("测试逐级上报机制")
    print("=" * 60)
    
    if not DingTalkConfig.LEADER_MAPPING:
        print("⚠️  未配置上级领导映射")
        print("   逐级上报功能将无法使用")
        return False
    
    print("上级领导映射：")
    for user_id, leader_id in DingTalkConfig.LEADER_MAPPING.items():
        user_info = DingTalkConfig.RESPONSIBLE_PERSONS.get(user_id, {})
        leader_info = DingTalkConfig.RESPONSIBLE_PERSONS.get(leader_id, {})
        print(f"   {user_info.get('name', user_id)} → {leader_info.get('name', leader_id)}")
    
    print("\n✅ 逐级上报配置正确")
    return True


def main():
    """主函数"""
    print("\n🔔 钉钉告警系统测试工具\n")
    
    # 测试配置
    if not test_config():
        print("\n❌ 配置检查失败，请先完成配置")
        return
    
    # 测试发送告警
    input("\n按回车键继续测试发送告警...")
    if not test_send_alert():
        print("\n❌ 发送测试失败")
        return
    
    # 测试逐级上报
    test_escalation()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n下一步：")
    print("1. 在 app.py 中集成告警服务")
    print("2. 在告警触发点调用 alert_handler.handle_zone_alert()")
    print("3. 启动应用测试实际告警功能")


if __name__ == "__main__":
    main()