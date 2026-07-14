# 接口与模块说明

## API 前缀

所有 HTTP 接口统一使用 `/api` 前缀。

## I01 IAuth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`

登录成功返回 `token` 和 `user`，前端在 `Authorization: Bearer <token>` 中携带。

## I02 IUser

- `GET /api/users/me`
- `PUT /api/users/me/password`

## I03 IFace

- `POST /api/faces/register`
- `GET /api/faces`
- `DELETE /api/faces/<id>`

## I04 IZone

- `GET /api/zones?camera_id=cam-1`
- `POST /api/zones`
- `PUT /api/zones/<id>`
- `DELETE /api/zones/<id>`

围栏点位格式：

```json
[
  { "x": 120, "y": 80 },
  { "x": 360, "y": 80 },
  { "x": 320, "y": 240 }
]
```

## I05 IAlarm

- `GET /api/alarms?page=1&pageSize=10&type=&severity=&status=`
- `POST /api/alarms`
- `PUT /api/alarms/<id>/handle`
- `GET /api/alarms/<id>/clip`

## I06 IDashboard

- `GET /api/dashboard/summary`

## I07 IAlarmStream

Socket.IO 事件：

- 客户端发送：`subscribe {"camera_ids":["cam-1"]}`
- 服务端发送：`alarm {...}`
- 客户端发送：`ack {"alarm_id":1}`
- 服务端发送：`heartbeat {"ts":"..."}`

## I08 IDetectionCallback

`backend/app/core_cv/pipeline.py` 中的 `DetectionPipeline.process_frame(camera_id, frame)` 会调用告警创建和 WebSocket 推送。

## I09 INotification

`backend/app/services/notification_svc.py` 提供：

- `push_dingtalk(alarm, escalation_level)`
- `check_escalation(alarm_id)`

## I10 IModelLoader

`backend/app/core_cv/model_loader.py` 提供：

- `get_yolo()`
- `get_face_detector()`
- `get_face_recognizer()`
- `warmup()`
# 多模态异常检测与主动活体

## 音视频联动

系统通过 5 秒滑动窗口融合三类证据：异常声音、人员情绪和电子围栏状态。单个弱信号不会直接产生高等级告警；尖叫/呼救等强声音可以独立触发，愤怒情绪与人员进入布防区同时出现时会触发联动告警。

- `POST /api/multimodal/audio-events`：接收 YAMNet 或其他声音分类器输出的标签与置信度。
- `POST /api/multimodal/emotion-events`：接收人脸情绪模型按跟踪对象输出的情绪与置信度。
- `POST /api/multimodal/evaluate`：结合人员是否处于布防区进行判定并创建告警。
- `POST /api/multimodal/analyze-wav`：对 16-bit PCM WAV 做轻量声学异常候选检测。该接口只识别高能量声学候选，不把音量阈值误报为语义明确的“打架”。

建议生产环境将 YAMNet 的 `Screaming`、`Shout`、`Yell`、`Glass breaking` 等标签接入 `audio-events`；“打架/争吵”需要使用现场数据微调的专用音频或音视频模型。

浏览器实时麦克风采集、WAV 分段分析、可选 YAMNet 语义分类及运行配置见 [audio_detection.md](audio_detection.md)。

## Aurora Guard 与随机动作

Aurora Guard 使用终端屏幕显示随机颜色/强度序列（light CAPTCHA），再通过人脸反射响应和深度分支联合判活。它要求可控光源与近距离摄像头，适用于门禁终端，不应直接套用到远距离监控流。

本项目保留原有 MiniFASNet 被动活体，并增加门禁侧随机动作挑战状态机：

- `POST /api/multimodal/liveness/challenges`：生成 2–4 个随机动作；
- `POST /api/multimodal/liveness/challenges/{id}/observations`：按顺序提交 `turn_left`、`turn_right`、`blink`、`open_mouth` 识别结果；
- `GET /api/multimodal/liveness/challenges/{id}`：查询挑战进度。

动作识别结果必须由门禁端的人脸关键点模型产生，服务端只接受置信度不低于 0.7、顺序正确且未超时的动作。后续接入真正的 Aurora Guard 时，应新增屏幕光序列生成、逐帧时间同步和光反射回归模型，不能仅用随机动作替代论文中的 light CAPTCHA。
