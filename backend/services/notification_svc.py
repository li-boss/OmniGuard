import requests


def send_dingtalk_alarm(webhook, payload):
    if not webhook:
        return False
    response = requests.post(webhook, json=payload, timeout=8)
    response.raise_for_status()
    return True
