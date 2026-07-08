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
