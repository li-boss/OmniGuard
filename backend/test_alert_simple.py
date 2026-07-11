"""
钉钉告警快速测试脚本
测试基本告警发送功能
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.dingtalk_alert import get_alert_service, DingTalkConfig
from datetime import datetime


def test_basic_alert():
    """测试基本告警发送"""
    print("=" * 60)
    print("钉钉告警测试")
    print("=" * 60)
    
    # 显示配置信息
    print(f"\n配置信息：")
    print(f"Webhook: {DingTalkConfig.WEBHOOK_URL[:50]}...")
    print(f"密钥: {DingTalkConfig.SECRET[:20]}...")
    print(f"\n责任人：")
    for user_id, info in DingTalkConfig.RESPONSIBLE_PERSONS.items():
        print(f"  - {info['name']} ({info['phone']})")
    
    print(f"\n响应超时: 30秒")
    
    # 发送测试告警
    print("\n" + "=" * 60)
    print("发送测试告警...")
    print("=" * 60)
    
    alert_service = get_alert_service()
    alert_service.start()
    
    alert_id = f"test_{int(datetime.now().timestamp())}"
    
    success = alert_service.send_alert(
        alert_id=alert_id,
        alert_level="high",
        alert_type="围栏入侵告警",
        alert_message="测试人员在测试区域停留超过30秒",
        responsible_person_id="user_001",
        extra_info={
            "区域名称": "测试区域A",
            "对象ID": "test_001",
            "摄像头": "cam-1"
        }
    )
    
    if success:
        print("\n✅ 告警发送成功！")
        print(f"告警ID: {alert_id}")
        print("\n请检查钉钉群是否收到消息")
        print("消息应该包含：")
        print("  - 告警类型")
        print("  - 区域名称")
        print("  - 告警等级")
        print("  - 发生时间")
        print("  - @高兴")
        
        print("\n等待30秒后将再次提醒...")
        print("责任人可以在钉钉群回复\"已处理\"确认告警")
        
        # 等待查看是否再次提醒
        import time
        for i in range(35):
            time.sleep(1)
            print(f"\r等待中... {i+1}/35秒", end='', flush=True)
        
        print("\n\n测试完成！")
    else:
        print("\n❌ 告警发送失败！")
        print("请检查：")
        print("  1. Webhook URL 是否正确")
        print("  2. 加签密钥是否正确")
        print("  3. 责任人手机号是否正确")
        print("  4. 网络连接是否正常")
    
    alert_service.stop()


def test_zone_alert():
    """测试围栏告警"""
    print("\n" + "=" * 60)
    print("测试围栏告警")
    print("=" * 60)
    
    from services.alert_handler import get_alert_handler
    
    alert_handler = get_alert_handler()
    alert_handler.start()
    
    success = alert_handler.handle_zone_alert(
        zone_id=1,
        zone_name="禁区A",
        object_id=123,
        duration=45.5,
        camera_id="cam-1"
    )
    
    if success:
        print("✅ 围栏告警发送成功！")
    else:
        print("❌ 围栏告警发送失败！")
    
    alert_handler.stop()


if __name__ == "__main__":
    print("\n🔔 钉钉告警功能测试\n")
    
    # 测试基本告警
    test_basic_alert()
    
    # 询问是否测试围栏告警
    choice = input("\n是否测试围栏告警？(y/n): ")
    if choice.lower() == 'y':
        test_zone_alert()
    
    print("\n" + "=" * 60)
    print("关于响应确认：")
    print("=" * 60)
    print("\n当前配置：责任人回复关键词自动确认")
    print("响应关键词：已处理、处理完成、收到、确认、已确认、完成")
    print("\n⚠️  注意：")
    print("要实现群消息监控，需要配置钉钉企业内部应用。")
    print("详细说明请查看：backend/services/dingtalk_message_monitor.py")
    print("\n替代方案：")
    print("1. 在前端系统手动确认")
    print("2. 通过API确认: POST /api/alerts/acknowledge")