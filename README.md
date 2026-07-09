# 智慧校园安防系统

这是按《6人团队分工与联调方案》重新生成的独立项目，目录位于 `D:\desktop\fengong`。项目采用前后端分离结构：后端负责鉴权、围栏、人脸、告警、WebSocket 和 CV 管线骨架；前端负责登录、大盘、告警历史、围栏配置和人脸管理。

## 技术栈

- 前端：Vue 3、Vite、Vue Router、Pinia、Element Plus、Socket.IO Client
- 后端：Flask、SQLAlchemy、Flask-SocketIO、JWT、SQLite
- 联调接口：`/api/auth`、`/api/users`、`/api/faces`、`/api/zones`、`/api/alarms`、`/api/dashboard`

## 启动

```powershell
.\setup.ps1
.\start-dev.ps1
```

也可以一键执行：

```powershell
.\one-click.ps1
```

访问地址：

- 前端：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:5000/api/system/health`
- 默认账号：`admin / admin123`

如果 5000 或 5173 已被占用，`start-dev.ps1` 会自动使用下一个可用端口，并在终端输出实际地址。

## 目录结构

```text
backend/
  app/
    api/          IAuth、IUser、IFace、IZone、IAlarm、IDashboard
    core_cv/      IModelLoader、IDetectionCallback、围栏判定、检测管线
    middleware/   JWT 鉴权
    models/       User、Face、Zone、Alarm、AccessLog
    services/     WebSocket、钉钉通知、日报、调度器
  tests/          后端基础测试
  run.py          后端入口

frontend/
  src/
    api/          Axios 接口封装
    components/   VideoPlayer、CanvasDraw、AlarmPopup
    router/       路由和登录守卫
    services/     WebSocket 客户端
    store/        Pinia 状态
    views/        Login、Dashboard、AlarmHistory、PerimeterConfig、FaceAccess

docs/             联调说明与演示流程
ops/              Jenkinsfile
```

## 团队分工映射

- A 前端 UI 与页面：`frontend/src/views`、`frontend/src/router`、`frontend/src/App.vue`
- B 前端组件与接口层：`frontend/src/components`、`frontend/src/api`、`frontend/src/store`、`frontend/src/services`
- C 后端鉴权与用户：`backend/app/api/user_api.py`、`backend/app/middleware`、`backend/app/models/user.py`
- D 后端 CV 推理管线：`backend/app/core_cv`、`backend/app/api/rule_api.py`、`backend/app/models/zone.py`
- E 后端告警与通知：`backend/app/api/event_api.py`、`backend/app/api/dashboard_api.py`、`backend/app/services`
- F CI/CD 与质量保障：`ops/Jenkinsfile`、`backend/tests`、`docs`

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests
```
