# 智能校园安全监测系统 - 后端 CV 推理管线用户手册 (User Manual)

本手册详细介绍了如何验证 YOLO 的可用性、如何使用本地摄像头进行实时测试，以及系统运行与部署的方法。

---

## 1. 验证 YOLOv8 及 CV 模型是否可用

我们已经准备了自动化的验证脚本与命令行单行程序。

### 方法 A：使用命令行单行程序（最快速）
在项目根目录（激活虚拟环境后）下，运行以下命令验证 YOLO 是否能够成功加载并推理：
```bash
# 确保已激活 backend/venv 虚拟环境
venv\Scripts\python.exe -c "from ultralytics import YOLO; import numpy as np; model = YOLO('core_cv/weights/yolov8n.pt'); res = model(np.zeros((640, 640, 3), dtype=np.uint8), verbose=False); print('【验证成功】YOLOv8 可正常工作！检测到框数:', len(res[0].boxes))"
```
*如果输出 `【验证成功】YOLOv8 可正常工作！检测到框数: 0`，说明 YOLOv8 模型权重和 Python 依赖均完全正常。*

### 方法 B：运行自动化测试套件
运行以下命令执行全部核心算法与人脸识别专项测试：
```bash
venv\Scripts\python.exe tests/test_cv_pipeline.py
```
*该测试会验证 YOLO 检测器、人脸识别边界及高并发读写锁、停留时间判定引擎、以及数据库/WebSocket 的全链路 Mock 闭环。*

---

## 2. 本地摄像头实时测试

后端推理管线设计上完全支持使用本地摄像头（USB摄像头或笔记本内置摄像头）进行实时推理测试。

我们在根目录下创建了一个轻量级的 live 测试脚本 [test_camera.py](file:///g:/vediomis/backend/test_camera.py)，它会直接打开您的默认摄像头，提取帧并在屏幕上绘制 YOLO 识别框与人脸标记。

### 运行摄像头 live 调试程序：
```bash
venv\Scripts\python.exe test_camera.py
```
* **绿色框**：代表 YOLO 成功识别出的人员（`Person`）。
* **蓝色框**：代表在人员区域内，YuNet 成功定位出的人脸（`Face`）。
* **退出**：在弹出窗口中按下 **`q` 键** 即可安全退出摄像头测试。

> [!TIP]
> **无法打开摄像头的排查方法**：
> 1. 请确保摄像头已连接，且没有被其他应用（如微信、钉钉、Zoom、浏览器等）独占使用。
> 2. 如果您有多个摄像头，可以在 `test_camera.py` 中修改 `camera_index = 0` 为 `1` 或其他数字。

---

## 3. 在 Flask 系统中集成真实摄像头

要在启动的主服务（`app.py`）中启用本地摄像头进行管线推理，请按照以下步骤操作：

### 步骤 1：启动后端 Web 服务与 WebSocket
```bash
venv\Scripts\python.exe app.py
```
*服务将在端口 `5000` 启动，并自动在后台热装载模型。*

### 步骤 2：通过 API 注册本地摄像头
使用 API 工具（如 Postman、ApiFox 或 `curl`）在数据库中创建一个 ID 为 `"0"` 的摄像头（`"0"` 代表系统默认的第 1 个摄像头）：
```bash
curl -X POST http://127.0.0.1:5000/api/zones \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "0",
    "name": "办公桌监控区",
    "polygon": [
      {"x": 0.0, "y": 0.0},
      {"x": 1.0, "y": 0.0},
      {"x": 1.0, "y": 1.0},
      {"x": 0.0, "y": 1.0}
    ],
    "stay_seconds": 5,
    "enabled": true,
    "distance_threshold": 0.0
  }'
```
* **`camera_id`: "0"**：让推理管线自动调用 `cv2.VideoCapture(0)` 提取您的真实摄像头流。
* **`polygon`**：这里设置的是全屏区域（$0,0$ 到 $1,1$）。只要您在摄像头前停留超过 5 秒（`stay_seconds`），系统就会触发报警。

### 步骤 3：查看状态与接收推送
1. 请求 `GET http://127.0.0.1:5000/api/cameras/status`，您可以看到摄像头 `"0"` 的实时连接状态。
2. 当您在摄像头前驻留超过 5 秒时：
   * 终端会打印黄色的 `Stay alert triggered` 报警提示。
   * 系统会自动将抓取的报警图片截屏存储在 `backend/static/snapshots/` 目录下。
   * 报警数据将异步持久化至 `AlarmEvent` 数据库中。
   * WebSocket 会即时向前端广播发送最新警报 JSON。

---

## 4. 关键配置项 (`config.py`)

可通过修改 `config.py` 或设置环境变量来调整以下关键阈值：

* **`ALARM_COOLDOWN_SECONDS`** (默认 `30` 秒)：防止同一个人在围栏里停留时不断产生大量重复报警记录。
* **`stay_seconds`** (在各监控区 polygon 属性中配置，默认 `5` 秒)：人员在围栏内的最短报警停留时长。
