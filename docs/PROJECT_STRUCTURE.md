# 项目目录结构说明

## 📁 目录结构

```
demo/
├── frontend/              # 前端项目
│   ├── src/
│   │   ├── api/          # API接口封装
│   │   ├── assets/       # 静态资源
│   │   ├── components/   # 公共组件
│   │   ├── router/       # 路由配置
│   │   ├── services/     # 服务层（WebSocket等）
│   │   ├── store/        # Pinia状态管理
│   │   ├── views/        # 页面组件
│   │   ├── App.vue       # 根组件
│   │   └── main.js       # 应用入口
│   ├── index.html        # HTML模板
│   ├── vite.config.js    # Vite配置
│   └── package.json      # 项目依赖
│
├── backend/              # 后端项目
│   ├── api/             # API路由
│   ├── models/          # 数据模型
│   ├── middleware/      # 中间件
│   ├── services/        # 业务服务
│   ├── core_cv/         # CV推理管线
│   ├── app.py           # 应用入口
│   └── requirements.txt # Python依赖
│
├── docs/                # 项目文档
│   └── PROJECT_STRUCTURE.md  # 本文档
│
├── ops/                 # CI/CD配置
│   └── Jenkinsfile      # Jenkins流水线
│
├── .gitignore           # Git忽略文件
├── README.md            # 项目说明
├── API_DOCUMENTATION.md # 接口文档
└── oprText.docx         # 项目需求文档
```

## 🔗 目录说明

### frontend/ - 前端项目
**负责人：** 人员A、B

**技术栈：**
- Vue 3 + Vite + Element Plus
- Vue Router + Pinia
- Axios + Socket.io-client

**开发命令：**
```bash
npm install    # 安装依赖
npm run dev    # 启动开发服务器
npm run build  # 构建生产版本
```

---

### backend/ - 后端项目
**负责人：** 人员C、D、E

**技术栈：**
- Python + Flask
- SQLAlchemy + JWT
- YOLO + OpenCV

**开发命令：**
```bash
pip install -r requirements.txt  # 安装依赖
python app.py                    # 启动服务器
```

---

### docs/ - 项目文档
**负责人：** 全员

**内容：**
- 项目结构说明
- 开发规范
- 部署文档
- 演示文档

---

### ops/ - CI/CD配置
**负责人：** 人员F

**内容：**
- Jenkins流水线配置
- Docker配置
- 部署脚本
- 监控配置

---

## 📝 文件引用规则

### 前端引用
```javascript
// 使用 @ 别名引用 src 目录下的文件
import { authApi } from '@/api/auth'
import Login from '@/views/Login.vue'
```

### 后端引用
```python
# 使用相对引用
from models.user import User
from middleware.auth_middleware import auth_required
```

### 文档引用
```markdown
# 使用相对路径
[接口文档](../API_DOCUMENTATION.md)
[项目说明](../README.md)
```

---

## 🚫 注意事项

1. **目录独立性**
   - frontend、backend、docs、ops 四个目录相互独立
   - 各目录有自己的依赖管理和配置文件

2. **路径引用**
   - 前端使用 `@/` 别名，不要使用相对路径
   - 后端使用相对导入
   - 文档使用相对路径

3. **文件位置**
   - API文档放在根目录：`API_DOCUMENTATION.md`
   - 项目说明放在根目录：`README.md`
   - 其他文档放在 `docs/` 目录

4. **不要混放**
   - 前端文件不要放在 backend 目录
   - 后端文件不要放在 frontend 目录
   - 文档文件不要放在代码目录

---

**最后更新：** 2026-07-07