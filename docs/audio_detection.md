# 实时声音检测

## 已实现链路

监控大盘中的“实时声音检测”由操作员手动启动。浏览器请求麦克风权限，将单声道音频编码为 16-bit PCM WAV，并按约 0.5 秒切片上传至：

```text
POST /api/multimodal/analyze-wav
```

后端始终运行轻量声学候选检测器，用于发现高能量高频人声和瞬态冲击声。启用 YAMNet 后，还会识别 AudioSet 中与安全相关的尖叫、喊叫、玻璃破碎、枪声等类别。检测结果进入 5 秒多模态融合窗口，并可与人员情绪和电子围栏状态共同触发告警。

每个摄像头默认有 30 秒声音告警冷却期，避免连续音频切片重复创建相同告警。新告警会写入数据库并通过 Socket.IO 推送到前端。

## 启用 YAMNet

YAMNet 是可选依赖。建议使用 TensorFlow 当前支持的 Python 版本建立部署环境，然后执行：

```powershell
pip install -r backend/requirements-audio.txt
$env:AUDIO_SEMANTIC_ENABLED = 'true'
```

首次识别时会从 TensorFlow Hub 加载官方模型并缓存。无法安装或加载 TensorFlow 时，基础检测器仍会继续工作，状态和错误可从以下接口读取：

```text
GET /api/multimodal/audio-status
```

## 配置

```dotenv
AUDIO_SEMANTIC_ENABLED=false
YAMNET_MODEL_URL=https://tfhub.dev/google/yamnet/1
AUDIO_CHUNK_SECONDS=0.5
AUDIO_ALARM_COOLDOWN_SECONDS=30
CAMERA_AUDIO_MONITOR_ENABLED=false
FFMPEG_PATH=ffmpeg
```

将 `CAMERA_AUDIO_MONITOR_ENABLED` 设为 `true` 后，后端会为配置中的 RTSP/RTMP/HTTP 摄像头源启动 FFmpeg 音轨解码。源没有音轨或暂时离线时会自动重连，运行状态会包含在 `audio-status` 响应的 `camera_audio_monitor` 字段中。

浏览器只会在操作员点击“开始检测”并授予权限后采集声音；点击“停止检测”或离开监控页面会立即释放麦克风。生产环境除 `localhost` 外应使用 HTTPS，否则浏览器通常会拒绝麦克风访问。

## 外部摄像头声音分类器

如果 RTSP/RTMP 摄像头已有独立的音频分析服务，可直接提交语义事件，无需经过浏览器麦克风：

```http
POST /api/multimodal/audio-events
Content-Type: application/json

{
  "camera_id": "cam-2",
  "label": "screaming",
  "confidence": 0.94
}
```

当前 MJPEG 预览格式本身不携带音轨，因此远程摄像头可以启用内置 FFmpeg 音轨监控，也可以由源端分类器接入上述事件接口。
