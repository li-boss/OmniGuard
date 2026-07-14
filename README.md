# 🛡️ OmniGuard - 智慧校园安防监测系统

OmniGuard 是一款专为智慧校园场景设计的高性能、实时视频流分析与边缘端推理系统。系统集成目标追踪、人脸识别、活体防伪、电子围栏检测、跌倒检测、火情检测以及异步告警流水线，为校园重点区域提供全天候智能化安全监测服务。

---

## ✨ 核心特性

### 1. 多模态安全检测
- **目标检测与追踪**：YOLOv8 检测 + SimpleTracker 多目标跨帧追踪
- **人脸识别与活体防伪**：YuNet 人脸检测 + MobileFaceNet 特征匹配 + 拉普拉斯方差活体检测
- **跌倒检测**：MediaPipe 姿态估计，检测人员跌倒行为
- **火情检测**：基于 HSV 颜色空间和 YOLO 的火情/烟雾检测

### 2. 智能告警系统
- **多边形电子围栏**：射线法碰撞检测，支持任意不规则图形防区
- **逗留时长检测**：毫秒级计时，超过阈值触发告警
- **告警去重冷却**：防止重复告警刷屏
- **多渠道通知**：WebSocket 实时推送 + 钉钉机器人通知

### 3. AI 智能日报
- **自动生成日报**：每天早上 6:00 自动生成过去 24 小时安全日报
- **手动生成日报**：支持手动生成任意时段的安全日报
- **AI 分析与建议**：使用轻量级 AI 模型分析告警数据，提供安全建议
- **PDF 导出**：支持导出 PDF 格式的日报文档

### 4. 高性能架构
- **非阻塞双缓冲**：Frame Grab/Retrieve 工作线程，消除视频流卡顿
- **自适应断线重连**：指数退避算法，保证 7×24 小时高可用
- **异步告警流水线**：线程安全队列削峰填谷，后台异步持久化

---

## 📁 项目目录结构

```text
OmniGuard/
├── backend/                      # 后端 Flask 与推理引擎
│   ├── api/                      # RESTful API 接口层
│   ├── core_cv/                  # 核心计算机视觉算法库
│   │   ├── weights/              # 模型权重目录
│   │   ├── yolo_detector.py      # YOLO 目标检测
│   │   ├── face_recognizer.py    # 人脸识别
│   │   ├── liveness_detector.py  # 活体检测
│   │   ├── fall_detector.py      # 跌倒检测
│   │   ├── fire_detector.py      # 火情检测
│   │   ├── rule_engine.py        # 围栏规则引擎
│   │   ├── stream_manager.py     # 视频流管理
│   │   └── pipeline.py           # 推理流水线
│   ├── models/                   # SQLAlchemy 数据模型
│   ├── services/                 # 业务服务层
│   ├── tests/                    # 测试用例
│   ├── app.py                    # Flask 应用入口
│   ├── config.py                 # 配置文件
│   └── requirements.txt          # Python 依赖
├── frontend/                     # 前端 Vue3 应用
│   ├── src/
│   │   ├── views/               # 页面组件
│   │   ├── components/          # 通用组件
│   │   ├── store/               # Pinia 状态管理
│   │   └── services/            # API 服务
│   ├── package.json             # 前端依赖
│   └── .env                      # 环境变量
└── README.md                     # 项目文档
```

---

## 🚀 快速开始

### 环境要求
- Python 3.9+（推荐 3.12）
- Node.js 18+
- SQLite 3
- 8GB+ 内存（AI 模型推理需要）

### 1. 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/macOS

# 安装依赖
pip install -r requirements.txt

# 下载模型权重（首次运行）
python core_cv/weights/download_weights.py

# 启动服务（首次启动会自动下载 AI 模型）
python app.py
```

**首次启动说明：**
- 系统会自动下载 Qwen2-1.5B-Instruct AI 模型（约 3GB）
- 使用国内镜像源加速下载（hf-mirror.com）
- 模型下载完成后，后续启动将直接加载本地模型

后端服务地址：`http://127.0.0.1:5000`

### 2. 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务地址：`http://127.0.0.1:3000`

### 3. 访问系统

浏览器打开 `http://127.0.0.1:3000`，使用默认账号登录：
- 用户名：`admin`
- 密码：`admin123`

### 4. 功能验证

登录后可验证以下功能：
- **实时监控**：主页查看摄像头实时画面
- **告警列表**：左侧导航"告警历史"查看告警记录
- **日报功能**：主页点击"生成日报"按钮，或左侧导航"日报列表"
- **围栏管理**：左侧导航"围栏管理"配置电子围栏
- **人脸库**：左侧导航"人脸库"管理人员人脸

---

## 🔧 核心功能配置

### 1. 摄像头配置
在 `backend/data/camera_streams.json` 中配置摄像头：
```json
{
    "cam-1": {
        "url": "0",
        "name": "前门摄像头",
        "enabled": true
    },
    "cam-2": {
        "url": "rtmp://example.com/live/cam01",
        "name": "后门摄像头",
        "enabled": true
    }
}
```

### 2. 钉钉告警通知
在 `backend/services/dingtalk_alert.py` 中配置钉钉机器人：
```python
class DingTalkConfig:
    WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
    SECRET = "YOUR_SECRET"  # 加签密钥
    
    # 责任人映射
    ALERT_TYPE_PERSON_MAPPING = {
        "围栏入侵告警": "wang_shihan",    # 汪士涵
        "陌生人告警": "wang_jinghang",    # 王靖杭
        "异常活动告警": "min_shiyu",      # 闵世宇
    }
```

### 3. AI 日报配置
日报功能配置（`backend/services/scheduler.py`）：
```python
# 定时任务配置
SCHEDULE_CONFIG = {
    "daily_report": {
        "trigger": "cron",
        "hour": 6,           # 每天 6:00 生成
        "minute": 0
    }
}

# 风险评分算法
# score = critical×10 + high×7 + medium×4 + low×1
# 风险等级：≤30 低，≤60 中，>60 高
```

### 4. 告警冷却时间
调整告警去重时间窗口（秒）：
```python
ALARM_COOLDOWN_SECONDS = 30  # 跌倒/火情告警冷却期
```

### 5. 人脸识别阈值
调整人脸匹配阈值（L2 距离）：
```python
FACE_MATCH_THRESHOLD = 0.32
```

### 6. AI 模型配置
在 `backend/services/ai_analyzer.py` 中配置 AI 模型：
```python
# 模型名称
MODEL_NAME = "Qwen/Qwen2-1.5B-Instruct"

# 生成参数
MAX_NEW_TOKENS = 512      # 最大生成长度
TEMPERATURE = 0.7          # 温度参数
TOP_P = 0.9               # Nucleus sampling
```

### 7. 钉钉逐级上报
配置逐级上报机制：
```python
# 上报超时时间（秒）
ESCALATION_TIMEOUT = 30

# 最大上报级别
MAX_ESCALATION_LEVEL = 2

# 领导映射
LEADER_MAPPING = {
    "wang_shihan": "gao_xing",  # 汪士涵的上级是高兴
}
```

---

## 🔌 核心 API 接口

### 认证接口
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/register` - 用户注册

### 摄像头管理
- `GET /api/cameras` - 获取摄像头列表
- `GET /api/cameras/status` - 获取摄像头运行状态
- `POST /api/cameras` - 添加摄像头
- `PUT /api/cameras/<id>` - 更新摄像头配置
- `DELETE /api/cameras/<id>` - 删除摄像头

### 围栏管理
- `GET /api/zones` - 获取围栏列表
- `POST /api/zones` - 创建围栏
- `PUT /api/zones/<id>` - 更新围栏
- `DELETE /api/zones/<id>` - 删除围栏

### 告警管理
- `GET /api/alarms` - 获取告警列表（支持分页、过滤）
- `GET /api/alarms/<id>` - 获取告警详情
- `POST /api/alarms` - 创建模拟告警
- `PUT /api/alarms/<id>/handle` - 处置告警
- `DELETE /api/alarms/<id>` - 删除告警

### 日报管理
- `POST /api/reports/generate` - 生成日报（支持自定义时间范围）
- `GET /api/reports` - 获取日报列表（支持分页）
- `GET /api/reports/<id>` - 获取日报详情
- `DELETE /api/reports/<id>` - 删除日报
- `GET /api/reports/<id>/download` - 下载日报 PDF

### 钉钉告警接口
- `POST /api/alerts/send` - 发送钉钉告警
- `POST /api/alerts/acknowledge` - 确认告警
- `GET /api/alerts/pending` - 获取待响应告警列表
- `POST /api/alerts/test` - 测试钉钉告警

### 人脸库管理
- `GET /api/faces` - 获取人脸库列表
- `POST /api/faces` - 添加人脸
- `DELETE /api/faces/<id>` - 删除人脸

### WebSocket 事件
- `connect` - 连接 WebSocket
- `subscribe` - 订阅摄像头告警
- `alarm:new` - 接收新告警推送
- `heartbeat` - 心跳检测

---

## 📊 告警类型说明

| 告警类型 | 英文标识 | 说明 | 责任人 |
|---------|---------|------|--------|
| 围栏入侵告警 | `electronic_fence` | 人员进入电子围栏区域并停留超时 | 汪士涵 |
| 陌生人告警 | `stranger` | 检测到未注册人脸或活体检测失败 | 王靖杭 |
| 异常活动告警——跌倒 | `fall` | 检测到人员跌倒行为 | 闵世宇 |
| 异常活动告警——火情 | `fire` | 检测到火情或烟雾 | 闵世宇 |

### 告警等级
- `critical` - 严重（停留 > 5 分钟）
- `high` - 高（停留 > 3 分钟）
- `medium` - 中（停留 > 1 分钟）
- `low` - 低（其他情况）

### 风险评分算法
```
风险评分 = min(critical × 10 + high × 7 + medium × 4 + low × 1, 100)

风险等级判断：
- 评分 ≤ 30：低风险
- 评分 ≤ 60：中风险
- 评分 > 60：高风险
```

### 逐级上报机制
1. **首次告警**：发送钉钉消息，@责任人
2. **30秒未响应**：再次提醒，@责任人 + @上级领导
3. **最多上报2级**：防止过度打扰

---

## 🧪 测试

### 运行后端测试
```bash
cd backend
pytest tests/
```

### 运行前端测试
```bash
cd frontend
npm run test
```

---

## 📝 开发说明

### 添加新的检测模块
1. 在 `backend/core_cv/` 创建检测器类
2. 在 `pipeline.py` 中集成检测逻辑
3. 在 `alarm_queue` 中推送告警数据

### 添加新的告警类型
1. 在 `backend/api/event_api.py` 的 `alarm_type_map` 中添加映射
2. 在 `backend/core_cv/pipeline.py` 中添加告警创建逻辑
3. 在 `backend/services/dingtalk_alert.py` 中配置责任人映射
4. 前端自动支持新的告警类型显示

### 自定义 AI 分析
1. 修改 `backend/services/ai_analyzer.py` 中的 `_build_prompt()` 方法
2. 调整提示词模板以适应特定需求
3. 或修改 `_fallback_analyze()` 实现自定义规则分析

### 自定义日报模板
1. 修改 `backend/services/pdf_generator.py` 中的 `generate()` 方法
2. 调整 PDF 布局和样式
3. 添加自定义章节或图表

### 架构文档
项目提供详细的架构文档，位于根目录：
- `异常行为检测模块架构文档.md` - 跌倒/火情检测模块设计
- `AI日报生成模块架构文档.md` - 日报生成模块设计
- `钉钉自动通知模块架构文档.md` - 钉钉通知模块设计

---

## 📄 许可证

MIT License

---

## 👥 贡献

欢迎提交 Issue 和 Pull Request！
