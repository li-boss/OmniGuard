# OmniGuard OpenSpec

> 文档版本：1.0  
> 基线：分支 `combineMonThirNight`，当前提交 `c66f43f3`；功能基线包含 `24cf644b`（通行日志）与 `8b8cb59f`（Swagger）
> 核验日期：2026-07-14  
> 证据范围：当前仓库源代码、目录结构、`README.md`、`docs/`、测试、`ops/Jenkinsfile`、`deploy/nginx-rtmp/README.md`、全部 Git 分支与提交记录。当前根目录未发现 `API_DOCUMENTATION.md`；旧接口说明仅存在于其他副本或历史提交，因此本文以当前已注册路由为准。当前工作树包含尚未提交的通行日志整合、10 秒去重、Swagger 补充及对应测试修改，本文按这些当前真实文件内容核验。

## 1. Project Overview

### 1.1 项目目标

OmniGuard 是面向校园监控场景的前后端一体化安防系统。当前代码将摄像头/网络流画面送入计算机视觉流水线，完成目标检测、跟踪、人脸识别与活体判断、电子围栏停留判断、跌倒及火情检测，并把检测结果持久化为告警、截图和录像，通过 WebSocket 与钉钉通道通知操作人员。系统同时提供告警处置、人员及人脸库、通行日志、监控大盘和安全日报功能。

### 1.2 使用场景

- 校园门口、楼宇入口等摄像头的实时 MJPEG 监看与人员识别。
- 对配置多边形围栏的区域进行人员进入/停留判断。
- 对跌倒、火焰/烟雾和人脸欺骗等异常生成告警证据。
- 管理员通过网页查看、筛选、处置、删除告警，预览截图并回放录像。
- 对已登记人员生成人脸通行记录；对告警进行 WebSocket 推送和钉钉通知。
- 汇总指定时段告警并生成、查询、删除和下载 PDF 日报。

### 1.3 系统价值

代码体现的价值是把实时视频分析、告警证据留存、通知、处置和统计整合为闭环。异步推理、告警队列、录像帧队列和摄像头重连机制用于降低视频读取、推理、数据库写入和 `VideoWriter` 初始化之间的相互阻塞。

### 1.4 事实边界

- 当前默认数据库是 SQLite（`backend/config.py`），也允许通过 `DATABASE_URL` 替换 SQLAlchemy URI；当前依赖中没有 MySQL 驱动。
- 当前人脸检测加载路径尝试使用 RetinaFace，特征模型加载 ArcFace `arcface_w600k_r50.onnx`；README 中的 YuNet/SFace、MobileFaceNet 描述与当前实现不一致。
- 模型权重、数据库、人脸样本和告警视频被 Git 忽略，仓库只交付下载逻辑与业务代码；模型能力依赖部署环境和权重可用性。
- 根目录当前没有 `API_DOCUMENTATION.md`。`docs/spec.md` 是较早接口说明，本文仅把与当前路由一致的内容作为辅助证据。

## 2. Requirement Specification

### REQ-001 用户认证与身份访问

- 需求描述：支持用户注册、登录、令牌刷新、查询本人信息和修改密码。
- 输入：用户名、密码及可选真实姓名/角色等字段；受保护接口使用 `Authorization: Bearer <token>`。
- 处理流程：`user_api.py` 校验请求，`User` 使用 Werkzeug 密码哈希，Flask-JWT-Extended 签发或校验 JWT，认证中间件解析当前用户。
- 输出：统一 JSON 响应，登录返回 token 和用户数据；冲突、缺参、无效/过期令牌返回对应 HTTP 状态。
- 验收标准：管理员可登录并访问 `GET /api/users/me`；重复用户名注册返回 409；无有效令牌不能访问受保护资源。

### REQ-002 人员与人脸库管理

- 需求描述：录入、查询、预览和删除人脸；录入学号不存在时自动创建用户并绑定真实 `user_id`。
- 输入：`studentId`、`name`、Base64 图片；删除时输入人脸记录 ID。
- 处理流程：解码图片，检测并裁剪人脸，提取及归一化特征，保存图片和 `RegisteredFace`；特征库定时/按需重载。
- 输出：人脸记录、图片预览、活动特征列表或明确的检测失败信息。
- 验收标准：无可检测人脸的图片必须拒绝；有效人脸记录关联 `User.id`；删除后列表不再返回该记录。

### REQ-003 实时人脸识别、活体与通行日志

- 需求描述：在人员检测框内识别人脸，区分已知人员、陌生人、分析中和欺骗攻击，并记录已知用户通行。
- 输入：摄像头帧、人员框、track ID、已登记特征库。
- 处理流程：RetinaFace 检测及五点对齐，ArcFace ONNX 特征比较；`LivenessDetector` 维护连续帧状态并可调用 MiniFASNetV2；时序投票稳定姓名。识别成功后按用户/摄像头 10 秒冷却写入 `AccessLog` 并更新 `last_recognized_at`。
- 输出：人脸框、姓名、真实用户 ID、距离/相似度及通行日志；欺骗攻击进入告警队列。
- 验收标准：匹配返回关联用户 ID，而不是人脸表 ID；同一用户短时间重复帧不重复写通行日志；欺骗结果不参与围栏正常身份判断。

### REQ-004 摄像头流与视频检测流水线

- 需求描述：读取本地摄像头或配置的视频源，输出带检测框和围栏叠加的 MJPEG 流。
- 输入：`backend/data/camera_streams.json` 中的摄像头映射、数据库围栏、视频帧。
- 处理流程：`StreamManager` 负责连接、重连和线程安全取帧；YOLO 检测 person；`SimpleTracker` 分配跨帧 ID；每个摄像头具有独立推理 worker 与双缓冲，管理器轮询各 pipeline。
- 输出：`/api/streams/<camera_id>.mjpg`、演示流、流配置和摄像头状态。
- 验收标准：默认配置摄像头即使没有围栏也初始化；切换源后标记 pipeline 为 dirty 并重建；停止时释放读取及推理线程。

### REQ-005 电子围栏规则

- 需求描述：管理摄像头多边形区域，并按人员停留时间触发围栏告警。
- 输入：camera ID、名称、至少三个点、停留秒数、启用状态。
- 处理流程：API 兼容 camelCase/snake_case 坐标；`RuleEngine` 用射线法和框中心/底部中心判断区域，维护对象进入时间和已触发状态。
- 输出：围栏 CRUD 数据、摄像头配置刷新以及 `围栏入侵告警` 队列项。
- 验收标准：区域内停留未到阈值不告警，超过阈值只触发一次，离开后状态重置；并发清理不破坏状态字典。

### REQ-006 异常行为检测

- 需求描述：检测跌倒以及火焰/烟雾，按冷却窗口生成告警。
- 输入：视频帧及可选人员框/模型权重。
- 处理流程：`FallDetector` 使用 MediaPipe 姿态几何规则；`FireDetector` 优先加载 YOLO 火情权重，缺失时使用 HSV 颜色区域回退；pipeline 依据检测结果和冷却时间投递告警。
- 输出：跌倒或火情检测结果与告警队列项。
- 验收标准：依赖/权重缺失时记录警告且主 pipeline 不崩溃；同类告警在冷却期内抑制重复触发。

### REQ-007 告警持久化、通知与处置

- 需求描述：保存告警、截图和检测数据，实时推送并支持查询、筛选、详情、处置和删除。
- 输入：pipeline 告警项或模拟告警请求；筛选分页参数；处置备注。
- 处理流程：`AlarmWorker` 先提交 `AlarmEvent` 获得稳定 ID，再尽力保存 `alarm_<id>.jpg`，启动录像并通过 Socket.IO 广播。通知服务/告警处理器可发送钉钉消息并进行确认与升级。
- 输出：告警 JSON、截图、Socket.IO `alarm` 事件和钉钉结果。
- 验收标准：截图失败不回滚已创建告警；处置后状态和处理时间更新；删除告警同时尽力清理录像与截图；未配置钉钉时不得伪报发送成功。

### REQ-008 告警录像与回放

- 需求描述：保存告警前后视频片段并供浏览器回放。
- 输入：摄像头采样帧、告警 ID、触发时刻；默认前录 5 秒、后录 10 秒、10 FPS。
- 处理流程：`AlarmVideoRecorder` 维护每路预缓冲和有界队列；后台线程分发帧；独立线程初始化 H.264 `VideoWriter`，初始化期间缓存帧并最多重试三次；结束后校验文件并写回 `video_path/clip_url`。启动时可把旧 mp4v/FMP4 转为浏览器兼容副本。
- 输出：`/static/videos/alarm_<id>.mp4` 或兼容副本，以及 `GET /api/alarms/<id>/video` 的分段文件响应。
- 验收标准：`VideoWriter` 初始化不能阻塞采集主线程；关闭时停止接收、排空队列、等待初始化线程并释放 writer；无有效文件时不把路径绑定到告警；回放接口支持浏览器 Range 请求。

### REQ-009 监控大盘与日报

- 需求描述：提供告警摘要/趋势，并生成安全日报和 PDF。
- 输入：告警数据、开始/结束时间、分页参数。
- 处理流程：dashboard 聚合数据库告警；日报服务统计等级与类型，调用 `AIAnalyzer`，模型不可用时使用规则回退，保存 `DailyReport` 并由 `PDFGenerator` 生成 PDF；调度器每日 06:00 执行日报任务。
- 输出：大盘汇总、日报列表/详情、PDF 下载。
- 验收标准：手动生成可指定时间范围；模型缺失仍能生成规则分析；风险分数按 `critical×10 + high×7 + medium×4 + low×1` 且上限 100。

### REQ-010 健康检查与部署运行

- 需求描述：暴露健康状态，支持 Waitress、Vite 开发代理、Jenkins 检查和可选 nginx-rtmp。
- 输入：环境变量、依赖、摄像头及 RTMP 配置。
- 处理流程：应用工厂初始化数据库/JWT/Socket.IO，非测试模式启动 pipeline、录像、调度、RTMP 和告警处理服务；`atexit` 注册清理。
- 输出：`GET /api/system/health` 返回服务、数据库、线程和活动流信息。
- 验收标准：测试模式不启动后台生产服务；生产退出时各服务执行 stop；前端可构建为静态文件。

### REQ-011 Swagger 接口文档管理

- 需求描述：通过 Swagger UI 集中展示并调试当前真实 API，不改变既有接口路径、业务逻辑或响应格式。
- 输入：浏览器访问文档端点；受保护接口通过 `Authorization: Bearer <token>` 传入 JWT。
- 处理流程：应用工厂使用 Flasgger `Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)` 注册 `backend/swagger_docs.py` 中的 Swagger 2.0 规格。
- 输出：`GET /apidocs/` 提供 Swagger UI，`GET /apispec_1.json` 提供机器可读规格；接口按认证、用户、人脸、告警、视频流、通行日志分类。
- 验收标准：两个文档端点可访问，规格包含 `BearerAuth`，文档中的 URL 与当前已注册路由一致，并可通过 Try it out 调用真实接口。

## 3. System Architecture

```text
Vue 3 / Element Plus / Pinia（含 AccessHistory）
          │ Axios + Socket.IO + MJPEG
          ▼
Flask API / JWT / Flask-SocketIO / Flasgger
          │
          ├── API 蓝图 ── 用户、人脸、围栏、告警、通行日志、日报、大盘、视频流
          ├── Swagger ── /apidocs/、/apispec_1.json、BearerAuth
          │
          ├── 业务服务 ── 通知、钉钉、日报、PDF、调度、录像、RTMP
          │
          ▼
CameraPipelineManager
          ├── StreamManager → 摄像头/RTSP/RTMP
          ├── YOLO + SimpleTracker
          ├── RetinaFace + ArcFace + 活体检测
          ├── MediaPipe 跌倒 / YOLO或HSV火情
          └── RuleEngine → alarm_queue → AlarmWorker
                                  │
                                  ├── SQLite / SQLAlchemy
                                  ├── 截图与 MP4
                                  ├── WebSocket
                                  └── 钉钉
```

前端 Axios 基址为 `/api`，Vite 代理后端；视频组件读取 MJPEG；WebSocket 客户端订阅 `cam-1`、`cam-2` 并在收到 `alarm` 后发送 `ack`。Flask 应用注册各蓝图并持有单例 `CameraPipelineManager`。视频取帧先提交录像预缓冲，再进入每摄像头独占推理 worker；推理结果异步回写，主循环叠加最新有效结果。告警采用有界 `alarm_queue` 削峰，`AlarmWorker` 在应用上下文内写库、截图、启动录像、推送 WebSocket，并调用告警处理器。

### 3.1 技术栈

| 层 | 当前代码/依赖 |
|---|---|
| 前端 | Vue 3.5、Vite 6、Element Plus、Pinia、Vue Router、Axios、socket.io-client、Lucide |
| API | Python、Flask 3.1、Flask-CORS、Flask-JWT-Extended、Flask-SocketIO、Flasgger 0.9.7.1、Waitress |
| 数据 | Flask-SQLAlchemy；默认 SQLite；JSON 字段；轻量启动迁移脚本 |
| CV/AI | OpenCV contrib、Ultralytics、ONNX Runtime、RetinaFace 包、MediaPipe、PyTorch/Transformers |
| 报告/任务 | ReportLab、APScheduler、Qwen2-1.5B-Instruct 下载逻辑与规则回退 |
| 运维 | Jenkinsfile、nginx-rtmp 说明、PowerShell 启动脚本在历史/副本中；当前根目录未保留 Dockerfile |

### 3.2 已实现模块

当前代码存在并已接线：认证与用户、人脸登记/特征库/识别、通行日志 API 与 AccessHistory 页面、围栏、摄像头流、YOLO 人员检测与跟踪、活体、跌倒、火情、告警 CRUD/截图/录像、WebSocket、钉钉通知、监控大盘、日报/PDF/调度、RTMP 推流、Swagger 接口管理、健康检查和 SQLite 字段兼容迁移。

## 4. Module Specification

### 4.1 用户认证模块

- 文件：`backend/api/user_api.py`、`backend/models/user.py`、`backend/middleware/auth_middleware.py`、`frontend/src/api/auth.js`、`frontend/src/store/auth.js`、`frontend/src/views/Login.vue`。
- API：`POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/refresh`、`GET /api/users/me`、`PUT /api/users/me/password`。
- 数据模型：`User(id, username, password_hash, role, real_name, phone, department, is_active, created_at)`。
- 功能：密码哈希、JWT、角色校验、默认管理员种子数据、前端路由守卫。

### 4.2 人脸识别模块

- 文件：`face_api.py`、`face_recognizer.py`、`liveness_detector.py`、`liveness_net.py`、`model_loader.py`、`models/face.py`、`models/access_log.py`。
- API：`POST /api/faces/register`、`GET /api/faces`、`GET /api/faces/features`、`GET /api/faces/<id>/image`、`DELETE /api/faces/<id>`。
- RetinaFace：`ModelLoader.get_face_detector()` 动态导入 RetinaFace detector；当前测试中的人脸生命周期用例已通过，但真实摄像头链路仍需实机验收。
- ArcFace：`ModelLoader.get_face_recognizer()` 加载 `arcface_w600k_r50.onnx` 到线程安全的 ONNX Runtime session；`FaceRecognizer` 对 112×112 对齐人脸提取并归一化特征。权重本身被 Git 忽略，需由下载脚本或部署环境提供。
- 活体检测：模糊度/纹理等规则和 MiniFASNetV2 ONNX 状态检测，按 track 累积结果。
- 特征库与匹配：`RegisteredFace.feature_data/feature_blob` 保存特征；识别器用 face ID 索引缓存，但匹配成功返回其中保存的 `user_id`。
- AccessLog：已知用户识别成功写入真实 `User.id`，同时更新 `last_recognized_at`；按用户执行 10 秒冷却，防止逐帧重复写入。

### 4.3 通行日志模块

- 文件：`backend/api/access_log_api.py`、`backend/models/access_log.py`、`backend/core_cv/pipeline.py`、`frontend/src/api/accessLog.js`、`frontend/src/views/AccessHistory.vue`、`frontend/src/router/index.js`。
- API：`GET /api/access-logs`、`POST /api/access-logs`、`GET /api/access-logs/<log_id>`、`DELETE /api/access-logs/<log_id>`；应用只注册 `access_log_bp`，不存在重复的 `GET /api/access-logs` 路由。
- 数据模型：`AccessLog.user_id` 外键指向 `User.id` 且允许为空；记录 `zone_id`、`confidence`、`device_code`、`access_method`、`direction`、`result`、`remark` 和 `created_at`。
- 自动写入：人脸匹配返回缓存元数据中的真实 `user_id`；pipeline 更新该用户关联人脸的 `last_recognized_at`，再创建 AccessLog。10 秒冷却用于抑制逐帧重复记录。
- 分页协议：请求使用 `page`、`pageSize`，后端兼容 `page_size`、`per_page`；响应数据包含 `items`、`total`、`page`、`pageSize`、`pages`，并保留兼容分页字段。
- 权限：普通用户只能查询自己的列表和详情，不能手工创建或删除；`admin`、`security` 可以查看全部、创建和删除。
- 前端：`/access-history` 路由加载 `AccessHistory.vue`，通过 `frontend/src/api/accessLog.js` 调用上述列表、详情和删除接口。

### 4.4 视频检测模块

- 文件：`stream_manager.py`、`yolo_detector.py`、`pipeline.py`、`fall_detector.py`、`fire_detector.py`、`stream_api.py`。
- 摄像头输入：JSON 映射支持本地序号和 URL；Windows 本地摄像头尝试 DirectShow；网络流使用 grab/retrieve 和重连退避。
- YOLO：`YoloDetector` 调用共享 `ModelLoader.get_yolo()`，pipeline 只保留 person 类结果。
- Pipeline：管理器维护 camera ID 到 pipeline；每路包含 stream、tracker、检测器、规则、推理 worker、双缓冲、最新叠加帧和录像器。
- API：`GET /api/cameras/status`、`GET /api/streams/<camera_id>.mjpg`、`GET /api/streams/demo.mjpg`、`GET /api/streams/config`、`POST /api/streams/cam-1/toggle_source`。

### 4.5 告警模块

- 文件：`models/alarm.py`、`api/event_api.py`、`services/ws_handler.py`、`notification_svc.py`、`alert_handler.py`、`dingtalk_alert.py`、`frontend/src/store/alarms.js`、`AlarmPopup.vue`、`AlarmHistory.vue`。
- 数据模型：`AlarmEvent` 保存类型、等级、摄像头/区域、截图/录像、描述、检测数据、坐标、状态、处理人/备注/时间、升级与钉钉状态、触发/创建/更新时间。
- API：`GET/POST /api/alarms`、`GET/DELETE /api/alarms/<id>`、`PUT /api/alarms/<id>/handle`、`GET /api/alarms/<id>/clip`、`GET /api/alarms/<id>/video`；钉钉端点为 `POST /api/alerts/send|acknowledge|test` 和 `GET /api/alerts/pending`。
- WebSocket：连接、断开、`subscribe`、`ack`；服务器发送 `alarm` 和 `heartbeat`。
- 截图：告警先落库，再保存 `backend/static/snapshots/alarm_<id>.jpg`；删除告警时清理候选截图文件。

### 4.6 视频录像模块

- 文件：`backend/services/alarm_video_recorder.py`、`backend/services/schema_migrations.py`、`backend/api/event_api.py`、`frontend/src/api/alarm.js`、`frontend/src/views/AlarmHistory.vue`。
- 生命周期：pipeline 持续提交采样帧形成预缓冲；告警触发创建 `_Recording`；录像后台线程按摄像头和时间窗写帧；到期或主动停止后释放 writer、校验视频并更新告警。
- MP4：优先 `avc1` H.264；旧编码视频可生成 `_browser.mp4`，不删除原文件；编码器不可用则记录失败且不虚构可播放路径。
- 回放：后端根据 `video_path` 定位受控静态目录并调用 `send_from_directory(..., conditional=True)`；前端以 blob URL 播放并在关闭时释放 URL。

### 4.7 接口文档管理

- 文件：`backend/swagger_docs.py`、`backend/app.py`、`backend/requirements.txt`。
- 配置：依赖为 `flasgger==0.9.7.1`；应用创建时调用 `Swagger(app, config=..., template=...)`，规格采用 Swagger 2.0。
- 地址：Swagger UI 为 `/apidocs/`，OpenAPI JSON 为 `/apispec_1.json`。
- 认证：`securityDefinitions` 定义 `BearerAuth`，受保护接口在文档中使用 `Authorization: Bearer <token>`。
- 分类：认证、用户、人脸、通行日志、告警和视频流；文档规格覆盖当前核心接口，包括通行日志列表、详情与删除。

## 5. Development Change Log

以下背景和原因均由提交差异与相邻历史归纳；提交未提供的信息标记为“无证据”。

### CHG-001 初始 CV 与活体能力

- 时间：2026-07-07 10:06—15:55 +08:00
- Commit：`17d24f97`、`06419087`、`33def18f`
- 问题：仓库只有初始脚手架，缺少可运行 CV 核心。
- 原因：建立视频检测、识别、规则和活体基础能力。
- 修改文件：`backend/core_cv/`、相关测试与导出。
- 实现：加入 stream、YOLO、人脸、规则、pipeline、模型加载和活体检测。
- 测试结果：历史包含测试套件提交；未发现该时点 CI 运行产物。

### CHG-002 前后端联调与模块合并

- 时间：2026-07-08 14:39—16:24 +08:00
- Commit：`bd658f39`、`54052921`、`d70b5015`、`20de5b1e`、`44412275`、`b270ede1`、`4b32fd1e`
- 问题：前端早期使用模拟数据，分支 B/C/E 的页面、认证、人脸和告警服务相互独立；API 字段与坐标格式不统一，并出现 Socket.IO 循环导入。
- 原因：形成可直接联调的一体化应用。
- 修改文件：前端 API/store/views，后端 API、models、app、ws_handler 和测试。
- 实现：移除 mock，兼容 camelCase/snake_case 与坐标映射，注册蓝图和 WebSocket 事件，合并用户/人脸/告警/调度/大盘，令 socketio 在 handler 中实例化以解除循环依赖。
- 测试结果：提交更新现有测试；无该批提交的独立 CI 报告。

### CHG-003 实时流与相机稳定性修复

- 时间：2026-07-09 09:20—2026-07-12 15:53 +08:00
- Commit：`909e4ff5`、`8356be25`、`462358ba`、`e39217d9`、`16f9f778`、`4136d901`、`671a03d1`、`b7b8485f`、`7dcbd6aa`、`fcd53ee5`
- 问题：MJPEG 端点缺失/失效，Windows MSMF 抓帧崩溃，本地摄像头 grab/retrieve 失败，帧竞争、框滞后、切源延迟和线程泄漏。
- 原因：保证多摄像头持续取帧并降低推理对画面更新的影响。
- 修改文件：`stream_api.py`、`stream_manager.py`、`pipeline.py`、`model_loader.py`、前端视频/摄像头 store 等。
- 实现：恢复动态 MJPEG；Windows 使用 DirectShow 回退；帧锁和深拷贝；独占推理 worker、双缓冲与生命周期清理；切源重建 pipeline；Waitress 多线程运行。
- 测试结果：历史说明包含 E2E 竞争修复；当前并发专项测试通过，完整结果见第 6 节。

### CHG-004 人脸 user_id 修复与识别闭环

- 时间：2026-07-13 16:04 +08:00
- Commit：`09dee715`
- 问题：特征缓存键是 `RegisteredFace.id`，旧匹配逻辑把该键当作用户 ID，通行日志可能关联错误主体；识别结果未完整落通行日志。
- 原因：人脸记录 ID 与用户 ID 是不同实体，必须保存并返回真实外键。
- 修改文件：`face_recognizer.py`、`pipeline.py`、`models/alarm.py`、录像/事件/前端文件等。
- 实现：缓存元数据加入 `face_id/user_id`，匹配返回 `info.user_id`；识别成功更新人脸最近识别时间并按 10 秒冷却创建 `AccessLog`。
- 测试结果：当前通行日志 API 生命周期测试通过；真实摄像头识别未在自动化测试中验证。

### CHG-005 告警回放页面修复

- 时间：2026-07-12 14:06—16:36 +08:00
- Commit：`c477bc18`、`2f077433`、`0fe864a9`
- 问题：告警页面缺少可用的截图预览和录像回放；截图字段/文件名不稳定，删除时可能残留文件。
- 原因：补齐告警证据查看与清理闭环。
- 修改文件：`event_api.py`、`pipeline.py`、`models/alarm.py`、`AlarmHistory.vue`、`AlarmPopup.vue`、Vite 配置。
- 实现：增加 video/clip 响应、前端 blob 播放、截图预览；先创建告警再以 ID 命名截图；序列化统一截图字段并在删除时清理。
- 测试结果：当前前端生产构建成功；仓库无前端组件测试文件，未验证真实浏览器编解码兼容性。

### CHG-006 告警录像生命周期修复

- 时间：2026-07-12 15:35—2026-07-13 11:55 +08:00
- Commit：`3a3a5a1a`、`0fe864a9`、`09dee715`、`a5f3f80a`
- 问题：录像服务曾在分支整理中丢失；告警前缓冲、结束、删除和应用退出时可能遗留队列、writer 或未完成初始化；manager 生命周期仅为局部变量。
- 原因：确保录像从触发前采样到应用退出都能确定性收尾。
- 修改文件：`alarm_video_recorder.py`、`schema_migrations.py`、`app.py`、`pipeline.py`、`event_api.py`。
- 实现：恢复完整服务；加入预缓冲、有界队列、到期完成、文件验证和数据库回写；关闭时停止接帧、排空队列、等待初始化；应用保存 `app.pipeline_manager` 并注册 recorder/manager stop。
- 测试结果：当前仓库没有针对 `AlarmVideoRecorder` 的自动化测试文件；只能确认代码路径与应用注册，不能宣称录像实机测试通过。

### CHG-007 VideoWriter 阻塞问题修复

- 时间：合并于 2026-07-13 16:04 +08:00
- Commit：`09dee715`（合并差异包含录像器异步初始化）
- 问题：`cv2.VideoWriter(... avc1 ...)` 初始化可能耗时，若在录像消费/采集路径同步执行会阻塞后续帧。
- 原因：隔离编码器初始化延迟并保留初始化期间的帧。
- 修改文件：`backend/services/alarm_video_recorder.py`。
- 实现：每个录像以 `AlarmVideoWriterInit-<id>` daemon 线程创建 writer；期间写入 `pending_frames`；全局锁串行化底层初始化；最多三次尝试，并记录耗时、丢帧和完成请求。
- 测试结果：没有专门测量阻塞时长或模拟卡住编码器的自动化测试；此项为代码级修复，性能验收证据不足。

### CHG-008 数据库配置与迁移事实核验

- 时间：2026-07-08 11:28、2026-07-09 10:55、2026-07-12 15:35 后续
- Commit：`15e1f928`、`4185dfe1`、`3a3a5a1a`
- 问题：数据模型字段演进需要兼容已有 SQLite 数据库；早期分支曾加入 `PyMySQL` 依赖。
- 原因：补充用户/人脸/门禁结构及告警录像字段，避免 `create_all()` 不修改旧表导致运行错误。
- 修改文件：历史 `.env.example`、requirements、模型/初始化；当前 `schema_migrations.py`。
- 实现：当前启动兼容脚本检查 `alarm_events`，缺失时分别补充 `video_path`、`triggered_at`、`snapshot_path` 三列。当前默认 URI 仍是 SQLite，当前 requirements 已无 PyMySQL；脚本没有执行跨数据库数据搬迁。
- 测试结果：没有 MySQL 迁移脚本、MySQL 连接配置、数据搬迁程序或 MySQL 集成测试。因此用户指定的“SQLite 迁移 MySQL”在本仓库不能判定为已完成；仅能确认“SQLite 兼容迁移”。

### CHG-009 异常检测、活体、通知和日报扩展

- 时间：2026-07-09 15:45—2026-07-13 14:57 +08:00
- Commit：`0632f5eb`、`40b970ee`、`4eba86ee`、`d51abdca`、`278ef208`、`58f23b54`
- 问题：初始 pipeline 缺少跌倒/火情、状态化防伪、自动钉钉上报和完整日报。
- 原因：扩展异常类型和处置/汇总能力。
- 修改文件：CV detectors、pipeline、告警/钉钉服务、日报模型/API/服务、PDF、前端页面。
- 实现：加入 MediaPipe 跌倒、YOLO/HSV 火情、MiniFASNetV2 活体、欺骗告警、钉钉确认/升级、日报统计/AI 回退/PDF/定时任务。
- 测试结果：当前测试未覆盖真实模型、钉钉网络或日报 PDF 内容；仅能确认模块已接入应用。

### CHG-010 CI、清理与部署配置

- 时间：2026-07-09—2026-07-13
- Commit：`03e1b529`、`f4571705`、`d71f60f5`、`586f0bb3` 至 `faa18e8d`、`60a4fc7a`
- 问题：流水线结构重复，仓库包含缓存、依赖、模型、数据库和生成媒体等大文件风险；最终需形成可交付干净基线。
- 原因：收敛 CI 阶段和版本控制内容。
- 修改文件：`ops/Jenkinsfile`、`.gitignore`、`.dockerignore`、仓库文件集、README。
- 实现：Jenkins 按前后端依赖、检查、测试、构建和报告组织；忽略虚拟环境、node_modules、模型、数据库、样本、告警媒体和 pytest 缓存；最终提交汇总当前系统。
- 测试结果：当前未发现 Jenkins 构建产物；本次本地验证见第 6 节。

### CHG-011 通行日志记录与前端展示

- 时间：2026-07-13
- Commit：`24cf644b`
- 问题：识别成功后的通行数据缺少完整的查询、详情、删除和前端展示闭环，分支中一度存在重复日志路由及分页参数差异。
- 原因：形成统一的通行历史模块，并确保日志主体使用真实 `User.id`。
- 修改文件：`backend/api/access_log_api.py`、`backend/models/access_log.py`、`backend/core_cv/pipeline.py`、`frontend/src/api/accessLog.js`、`frontend/src/views/AccessHistory.vue`、前端路由及导航。
- 实现：保留单一 `access_log_bp`；提供列表、创建、详情和删除接口；统一 `page/pageSize` 并兼容旧分页参数；普通用户仅可读取本人记录，`admin/security` 可查看全部并创建、删除；识别写日志冷却最终为 10 秒。
- 测试结果：新增通行日志集成测试覆盖唯一列表路由、10/50 分页、角色权限、真实用户 ID、最近识别时间和去重；相关用例通过。

### CHG-012 Swagger 接口文档

- 时间：2026-07-14
- Commit：`8b8cb59f`
- 问题：后端真实接口缺少统一、可交互的接口管理入口。
- 原因：满足开发联调与结题接口文档交付要求，同时保持业务接口路径和响应不变。
- 修改文件：`backend/app.py`、`backend/swagger_docs.py`、`backend/requirements.txt`。
- 实现：接入 Flasgger；提供 `/apidocs/` 和 `/apispec_1.json`；配置 `BearerAuth`；按认证、用户、人脸、告警、视频流和通行日志分类。
- 测试结果：运行验证中 Swagger UI 与规格 JSON 返回 HTTP 200，规格包含通行日志接口和 Bearer 认证定义。

### CHG-013 combineMonThirNight 合并

- 时间：2026-07-14
- Commit：`c66f43f3`
- 问题：Swagger、录像与人脸闭环修改需要和伙伴新增的 AccessLog API、模型及 AccessHistory 页面汇合。
- 原因：形成包含双方功能的统一分支版本。
- 修改文件：合并提交覆盖前后端相关模块；后续工作树进一步整理通行日志重复路由、分页、权限、10 秒去重及 Swagger 文档。
- 实现：保留现有人脸识别、录像和 Swagger 能力，并接入通行历史页面与 AccessLog API；当前路由检查不存在重复的 `GET /api/access-logs`。
- 测试结果：后端 25 项测试中 24 项通过，唯一失败为历史围栏告警类型契约；前端生产构建成功。

## 6. Testing Specification

### 6.1 测试资产

| 分类 | 文件/范围 | 覆盖内容 |
|---|---|---|
| 接口测试 | `test_auth.py`、`test_health.py`、`test_alarm_flow.py`、`test_face_register.py`、`test_access_log_integration.py` | 登录/本人、重复注册、健康、围栏-模拟告警-处置、人脸及通行日志 API、分页、权限和识别写日志闭环 |
| CV 单元测试 | `test_cv_pipeline.py` | IoU、tracker、点在多边形、停留规则、stream mock、人脸比较/并发、pipeline API/E2E |
| 并发测试 | `test_pipeline_multi_worker.py`、`test_rule_engine_concurrency.py` | 多摄像头 worker 隔离、阻塞检测器不拖慢其他路、规则状态并发安全 |
| 手工/环境脚本 | `test_camera.py`、`test_alert_*.py`、`test_dingtalk.py`、`check_alarms.py` | 摄像头、告警配置、钉钉和数据库检查；不属于 pytest 自动验收集 |
| 前端 | `vitest.config.js` 存在，但当前仓库未发现 `*.test.*`/`*.spec.*` 前端测试 | 只能执行构建级验证 |

### 6.2 本次实际运行记录（2026-07-14）

- 命令：`python -m pytest tests -q`（目录 `backend`）。
- 结果：25 项，24 通过、1 失败，47 个 warning。
- 唯一失败：`TestCameraPipelineE2E.test_pipeline_e2e_alarm_trigger_and_db_write` 期望告警类型 `electronic_fence`，当前 pipeline 实际产生中文围栏告警类型。这是已有测试契约与当前实现不一致，不是本次 Swagger 或通行日志修改引入。
- 其余结果：人脸生命周期和新增通行日志集成测试通过；除上述历史告警类型测试外，其余新增功能测试通过。warning 包含依赖/权重环境提示以及 JWT、时间 API 和 SQLAlchemy 旧接口提示，不能据此宣称真实模型或硬件链路已经验收。
- 命令：`npm.cmd run build`（目录 `frontend`）。
- 结果：成功，Vite 转换 3471 个模块并生成 `dist`；Rollup 对 `@vueuse/core` 的 PURE 注释给出非阻塞警告。
- Git 工作树：当前除本文外仍有通行日志整合相关源代码差异；文档据当前工作树真实状态编写，未将这些差异误写为已提交内容。

### 6.3 验收矩阵与缺口

| 类别 | 当前证据 | 判定 |
|---|---|---|
| 接口测试 | 认证、健康、人脸生命周期、通行日志分页/权限/闭环通过；围栏告警类型断言失败 | 除历史告警类型契约外通过 |
| AI 模型测试 | mock/算法单元存在；真实权重及依赖不完整 | 未完成实模验收 |
| 录像测试 | 无专用自动化用例，无本次真实 MP4/Range 播放记录 | 未验收 |
| 数据库测试 | 测试使用 SQLite；CRUD/关系部分覆盖 | SQLite 部分通过；MySQL 未测试且未实现迁移 |
| 前后端联调 | API 封装与后端路由已对应，前端构建成功 | 代码级接通；缺真实浏览器 E2E |
| 钉钉/RTMP | 存在服务和手工脚本 | 无外部服务验收证据 |

建议的正式验收步骤：安装锁定版本依赖与全部权重；用真实人脸样本执行注册/识别/活体；用可控视频触发围栏、跌倒、火情和欺骗告警；核对数据库、截图、告警前后 MP4、HTTP Range 回放、WebSocket、钉钉；并在 CI 中归档 pytest、前端测试和浏览器 E2E 报告。

## 7. Final Acceptance Report

### 7.1 已完成

- 前后端应用骨架、JWT 认证、页面路由及真实 API 封装。
- 用户、人脸、围栏、告警、通行日志、日报等 SQLAlchemy 模型与 API。
- 通行日志列表、创建、详情和删除接口，`page/pageSize` 分页兼容、分角色访问控制及 `/access-history` 前端页面。
- 摄像头流读取、MJPEG、YOLO 人员检测、跟踪、围栏停留规则与叠加显示。
- RetinaFace/ArcFace 加载与人脸匹配逻辑、状态化活体、真实 user ID 回传及通行记录。
- 跌倒、火情/烟雾检测代码和告警冷却。
- 告警异步落库、截图、WebSocket、钉钉服务、处置与删除。
- 告警前后帧录像、异步 VideoWriter 初始化、MP4 路径回写及回放 API/页面。
- Flasgger Swagger 2.0 接口管理、`/apidocs/`、`/apispec_1.json`、Bearer JWT 定义及六类核心接口文档。
- 大盘、日报生成、规则回退分析、PDF 和定时任务。
- RTMP 推流服务、健康检查、Waitress 运行、Jenkins 配置和模型下载逻辑。

### 7.2 未完成或无验收证据

- 未完成 SQLite 到 MySQL 的迁移；当前仍默认 SQLite，也没有 MySQL 驱动、迁移/回滚脚本或 MySQL 测试。
- ArcFace 业务代码已接入且人脸生命周期自动化用例通过，但仓库未跟踪权重，真实摄像头、真实人脸和活体攻击链路仍没有正式验收报告。
- 自动化测试未全绿（24/25）；唯一失败是测试期待英文 `electronic_fence`、实现返回中文围栏告警类型的历史契约问题。真实 AI 模型、录像、浏览器回放、钉钉、RTMP 和多路长稳仍没有正式测试报告。
- 前端没有 Vitest 用例，也没有 Playwright/Cypress 等端到端测试。
- 当前仓库缺少根目录 `API_DOCUMENTATION.md`；旧 `docs/spec.md` 与现状存在偏差。

### 7.3 风险

- 依赖/权重风险：模型权重不随仓库交付，真实 RetinaFace、ArcFace、MiniFASNet、MediaPipe、Transformers 和火情模型能力仍取决于部署环境；自动化用例通过不等同于真实视频链路验收。
- 编码风险：OpenCV 构建若不支持 `avc1`，告警录像无法生成；虽有失败保护，但业务证据会缺失。
- 并发与资源风险：大量线程、每摄像头推理 worker、录像初始化线程和 Waitress 100 线程需要长稳与资源上限测试。
- 数据演进风险：`db.create_all()` 加单列 SQLite 补丁不能替代版本化迁移；后续模型变更容易与既有数据库不一致。
- 安全风险：默认密钥和默认管理员密码适合开发，不适合生产；CORS 当前允许 `/api/*` 任意来源；人脸图片和视频访问控制需复核。
- 契约风险：中文/英文告警类型、README 模型描述、旧 spec 和当前代码不一致，已导致自动化测试失败。

### 7.4 后续优化

1. 锁定 RetinaFace/ArcFace/MiniFASNet/MediaPipe/Transformers 依赖，提供可复现权重清单与离线校验值，并统一围栏告警类型契约，使 25 项后端测试全绿。
2. 为录像器增加假 VideoWriter 的阻塞、失败、重试、排队、关闭和 Range 回放测试，并做真实浏览器编码兼容测试。
3. 若业务确需 MySQL，使用 Alembic/Flask-Migrate 设计 SQLite→MySQL 数据迁移、校验和回滚，而不是仅修改连接串。
4. 统一告警类型枚举和 API schema，更新 README/API 文档与测试；明确当前 RetinaFace + ArcFace 的真实模型组合。
5. 增加前端组件及 E2E 测试，覆盖登录、画流、围栏绘制、告警推送、截图、回放、处置和日报下载。
6. 生产部署时强制外部密钥、修改默认管理员、限制 CORS，评估媒体与人脸数据鉴权、保存周期及审计。

---

本文没有把不存在的 MySQL 迁移或未执行的实机测试写成已完成功能；Swagger、通行日志、人脸闭环与录像能力按当前代码和已执行验证认定，未把缺少权重、真实摄像头、真实录像及外部服务测试的情况写成验收通过。当前结论为“除历史围栏告警类型测试外，其余新增功能测试通过”，不等同于全部测试通过。所有结论均受上述仓库基线、当前工作树和本次运行环境约束。
