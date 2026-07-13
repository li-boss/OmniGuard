# 成员文件映射

| 成员 | 模块 | 主要目录 |
| --- | --- | --- |
| A | 前端 UI 与页面 | `frontend/src/views`, `frontend/src/router`, `frontend/src/App.vue` |
| B | 前端组件与接口层 | `frontend/src/components`, `frontend/src/api`, `frontend/src/store`, `frontend/src/services` |
| C | 后端鉴权与用户 | `backend/app/api/user_api.py`, `backend/app/models/user.py`, `backend/app/middleware` |
| D | 后端 CV 推理管线 | `backend/app/core_cv`, `backend/app/api/rule_api.py`, `backend/app/models/zone.py` |
| E | 后端告警与通知 | `backend/app/api/event_api.py`, `backend/app/api/dashboard_api.py`, `backend/app/services` |
| F | CI/CD 与质量保障 | `ops/Jenkinsfile`, `backend/tests`, `docs` |
