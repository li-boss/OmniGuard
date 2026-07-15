# 教室异常声音实时识别

本模块使用 Google YAMNet 预训练模型识别爆炸声和玻璃破碎声。YAMNet 输出 AudioSet 的 521 个环境声音类别，本项目将相关原始类别合并为两个业务类别，并复用现有 `alarm_queue -> AlarmWorker -> AlarmEvent -> WebSocket -> 前端` 告警链路。

## 环境安装

优先使用项目当前可正常安装 TensorFlow 的 Python 环境。TensorFlow 在不同 Python 版本和 Windows 平台上的可用版本不同；如果当前环境无法安装，可改用 Python 3.10 或 3.11 创建独立环境。

```powershell
cd D:\main\OmniGuard
py -3.11 -m venv .venv-audio
.\.venv-audio\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pip install -r backend\requirements-audio.txt
```

依赖文件包含 `setuptools<81`，用于兼容 TensorFlow Hub 当前仍使用的 `pkg_resources`。

首次启动声音识别时，TensorFlow Hub 会下载 `https://tfhub.dev/google/yamnet/1`。模型加载失败不会影响视频、人脸和围栏功能，API 会返回可读错误。

模型缓存固定在 `backend/core_cv/weights/tfhub`。首次下载需要联网且可能耗时较长，后续启动会复用本地缓存。

如果 TensorFlow Hub 内部下载出现 TLS 错误，程序会自动通过 `requests` 下载同一官方压缩包，并保存到 `backend/core_cv/weights/yamnet` 后从本地加载。

## 启动

```powershell
cd D:\main\OmniGuard\backend
python app.py
```

前端：

```powershell
cd D:\main\OmniGuard\frontend
npm run dev
```

登录后打开“声音”页面，选择电脑或 USB 麦克风，点击“启动”。点击“停止”会关闭输入流并释放麦克风。

## 麦克风选择

页面会通过 `/api/audio-detection/devices` 列出所有具有输入通道的设备。也可以在 `backend/config/audio_detection.json` 中设置默认设备编号：

```json
{
  "input_device": 1
}
```

设备不可用、被其他程序占用或缺少系统权限时，页面会显示“无法打开麦克风”的错误。

## 阈值与确认

配置文件：`backend/config/audio_detection.json`

```json
{
  "thresholds": {
    "explosion": 0.45,
    "glass_break": 0.35
  },
  "confirmation_count": 2,
  "cooldown_seconds": 3.0
}
```

- `explosion`：爆炸声阈值。
- `glass_break`：玻璃破碎声阈值。
- `confirmation_count`：连续超过阈值的次数，默认 2。
- `cooldown_seconds`：同类声音触发后的冷却时间，默认 3 秒。

阈值修改后需要重启后端。建议先使用 WAV 测试真实音效，再小幅调整；降低阈值会提高召回率，也会增加拍手、关门等误报。

## 类别合并

爆炸声匹配：

```text
Explosion, Boom, Fireworks
```

玻璃破碎声匹配：

```text
Glass, Shatter, Breaking, Smash, crash
```

实时输入统一为 16 kHz、单声道、float32。检测窗口为 0.96 秒，步长为 0.48 秒。

## WAV 离线测试

支持不同采样率、单声道或多声道 WAV；入口会转换为 16 kHz 单声道 float32。

```powershell
cd D:\main\OmniGuard\backend
python scripts\test_audio_wav.py D:\audio\explosion.wav
python scripts\test_audio_wav.py D:\audio\glass_break.wav
```

输出包含业务类别、置信度、YAMNet 原始类别和检测时间。

保存 1024 维 YAMNet embedding：

```powershell
python scripts\test_audio_wav.py D:\audio\explosion.wav --save-embedding D:\audio\explosion_embedding.npy
```

该接口仅预留后续“爆炸声、玻璃破碎声、其他声音”三分类训练能力。当前没有训练数据和额外分类器，不对 embedding 方案的准确率作任何承诺。

## 告警与日志

触发后会创建：

- `alarm_type=异常声音告警`
- 爆炸声等级为 `critical`
- 玻璃破碎声等级为 `high`
- `detection_data` 保存类别、置信度、YAMNet 原始类别和时间

事件进入原有 AlarmWorker，写入 AlarmEvent，并继续执行截图、录像启动、WebSocket 和前端告警展示。声音告警日志写入：

```text
backend/logs/audio_alerts.log
```

如果对应摄像头没有画面，告警仍会入库，但证据截图使用“Audio event detected”占位画面。

## 测试

```powershell
cd D:\main\OmniGuard\backend
python -m pytest tests\test_audio_event_detector.py -q
```

测试覆盖类别合并、分类阈值、连续确认、低分重置和冷却时间。

## 已知限制

- YAMNet 是通用 AudioSet 模型，教室声学环境、麦克风距离和播放设备都会影响置信度。
- 拍手、重物落地和关门可能与爆炸类声学特征相似，需要结合现场 WAV 调整阈值。
- 前端停止按钮依赖后端进程仍可响应；进程正常退出时也会注册释放函数。
- 当前不使用 Whisper，因为本功能是环境声音分类，不是语音转文字。
