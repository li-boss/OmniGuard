# 智慧校园安防系统 - 接口文档

## 📋 文档说明

本文档记录了前端项目中所有API接口的定义、开发状态、模拟数据使用情况，以及联调时需要修改的内容。

---

## 🔌 接口总览

| 接口编号 | 接口名称 | 负责人 | 文件路径 | 开发状态 | 使用页面 |
|---------|---------|--------|---------|---------|---------|
| I01 | IAuth (鉴权接口) | C | `api/auth.js` | ✅ 已封装 | Login |
| I02 | IUser (用户管理接口) | C | `api/user.js` | ✅ 已封装 | App |
| I03 | IFace (人脸管理接口) | C | `api/face.js` | ✅ 已封装 | FaceAccess |
| I04 | IZone (围栏配置接口) | D | `api/zone.js` | ✅ 已封装 | PerimeterConfig |
| I05 | IAlarm (告警查询与处置接口) | E | `api/alarm.js` | ✅ 已封装 | AlarmHistory |
| I06 | IDashboard (大盘统计接口) | E | `api/dashboard.js` | ✅ 已封装 | Dashboard |

---

## 📝 接口详细说明

### I01 - IAuth (鉴权接口)

**负责人：** C  
**后端文件：** `backend/api/user_api.py`, `backend/middleware/auth_middleware.py`  
**前端文件：** `frontend/src/api/auth.js`

#### 接口方法

| 方法 | 路径 | 说明 | 开发状态 |
|------|------|------|---------|
| POST | `/api/auth/register` | 用户注册 | ✅ 已定义 |
| POST | `/api/auth/login` | 用户登录 | ✅ 已定义 |
| POST | `/api/auth/refresh` | 刷新token | ✅ 已定义 |

#### 使用位置

- **Login.vue** - 登录页调用登录接口

#### 模拟数据使用情况

✅ **已使用模拟数据**

**文件位置：** `frontend/src/api/auth.js`  
**模拟函数：** `authApiMock`

```javascript
// 模拟登录实现
async login(data) {
  await new Promise(resolve => setTimeout(resolve, 500))
  return {
    token: 'mock-token-' + Date.now(),
    user: { id: 1, username: data.username, role: 'admin' }
  }
}
```
<!--  -->
#### 联调修改指南

**修改文件：** `frontend/src/views/Login.vue`

```javascript
// ❌ 删除或注释模拟API调用
// const response = await authApiMock.login(loginForm)

// ✅ 启用真实API调用
const response = await authApi.login(loginForm)
```

---

### I02 - IUser (用户管理接口)

**负责人：** C  
**后端文件：** `backend/api/user_api.py`, `backend/models/user.py`  
**前端文件：** `frontend/src/api/user.js`

#### 接口方法

| 方法 | 路径 | 说明 | 开发状态 |
|------|------|------|---------|
| GET | `/api/users/me` | 获取当前用户信息 | ✅ 已定义 |
| PUT | `/api/users/me/password` | 修改密码 | ✅ 已定义 |

#### 使用位置

- **App.vue** - 可用于显示用户信息（当前未使用）

#### 模拟数据使用情况

✅ **已使用模拟数据**

**文件位置：** `frontend/src/api/user.js`  
**模拟函数：** `userApiMock`

#### 联调修改指南

**修改文件：** `frontend/src/App.vue`（如需使用）

```javascript
// ❌ 删除模拟API
// const data = await userApiMock.getCurrentUser()

// ✅ 启用真实API
const data = await userApi.getCurrentUser()
```

---

### I03 - IFace (人脸管理接口)

**负责人：** C  
**后端文件：** `backend/api/face_api.py`, `backend/models/face.py`  
**前端文件：** `frontend/src/api/face.js`

#### 接口方法

| 方法 | 路径 | 说明 | 开发状态 |
|------|------|------|---------|
| POST | `/api/faces/register` | 注册人脸 | ✅ 已定义 |
| GET | `/api/faces` | 获取人脸列表 | ✅ 已定义 |
| DELETE | `/api/faces/<id>` | 删除人脸 | ✅ 已定义 |
| PUT | `/api/faces/<id>` | 更新人脸信息 | ✅ 已定义 |
| GET | `/api/faces/stats` | 获取统计信息 | ✅ 已定义 |
| GET | `/api/faces/<id>/logs` | 获取识别记录 | ✅ 已定义 |

#### 使用位置

- **FaceAccess.vue** - 人脸管理页面

#### 模拟数据使用情况

✅ **已使用模拟数据**

**文件位置：** `frontend/src/api/face.js`  
**模拟函数：** `faceApiMock`  
**模拟数据：** 3条人脸记录

```javascript
mockFaces: [
  { id: 1, name: '张三', employeeId: 'EMP001', ... },
  { id: 2, name: '李四', employeeId: 'EMP002', ... },
  { id: 3, name: '王五', employeeId: 'EMP003', ... }
]
```

#### 联调修改指南

**修改文件：** `frontend/src/views/FaceAccess.vue`

需要修改的函数：
1. `loadFaceList()` - 获取人脸列表
2. `loadStats()` - 获取统计信息
3. `handleViewFace()` - 获取识别记录
4. `handleDeleteFace()` - 删除人脸
5. `handleSubmitFace()` - 注册/更新人脸

```javascript
// 示例：loadFaceList函数
// ❌ 删除模拟API
// const response = await faceApiMock.getList({...})

// ✅ 启用真实API
const response = await faceApi.getList({...})
```

---

### I04 - IZone (围栏配置接口)

**负责人：** D  
**后端文件：** `backend/api/rule_api.py`, `backend/models/zone.py`  
**前端文件：** `frontend/src/api/zone.js`

#### 接口方法

| 方法 | 路径 | 说明 | 开发状态 |
|------|------|------|---------|
| GET | `/api/zones?camera_id=` | 获取围栏列表 | ✅ 已定义 |
| POST | `/api/zones` | 创建围栏 | ✅ 已定义 |
| PUT | `/api/zones/<id>` | 更新围栏 | ✅ 已定义 |
| DELETE | `/api/zones/<id>` | 删除围栏 | ✅ 已定义 |

#### 使用位置

- **PerimeterConfig.vue** - 围栏配置页面

#### 模拟数据使用情况

✅ **已使用模拟数据**

**文件位置：** `frontend/src/api/zone.js`  
**模拟函数：** `zoneApiMock`  
**模拟数据：** 3个摄像头，2个围栏

```javascript
mockCameras: [
  { id: 1, name: '东门摄像头', status: 'online' },
  { id: 2, name: '西门摄像头', status: 'online' },
  { id: 3, name: '北门摄像头', status: 'offline' }
]

mockZones: [
  { id: 1, name: '禁区A', type: 'forbidden', ... },
  { id: 2, name: '警戒区B', type: 'warning', ... }
]
```

#### 联调修改指南

**修改文件：** `frontend/src/views/PerimeterConfig.vue`

需要修改的函数：
1. `loadCameraTree()` - 获取摄像头树
2. `loadZoneList()` - 获取围栏列表
3. `handleToggleZone()` - 切换围栏状态
4. `handleDeleteZone()` - 删除围栏
5. `handleSubmitZone()` - 创建/更新围栏

```javascript
// 示例：loadZoneList函数
// ❌ 删除模拟API
// zoneList.value = await zoneApiMock.getList({...})

// ✅ 启用真实API
zoneList.value = await zoneApi.getList({...})
```

---

### I05 - IAlarm (告警查询与处置接口)

**负责人：** E  
**后端文件：** `backend/api/event_api.py`, `backend/models/alarm.py`  
**前端文件：** `frontend/src/api/alarm.js`

#### 接口方法

| 方法 | 路径 | 说明 | 开发状态 |
|------|------|------|---------|
| GET | `/api/alarms?page=&type=&severity=` | 获取告警列表 | ✅ 已定义 |
| PUT | `/api/alarms/<id>/handle` | 处置告警 | ✅ 已定义 |
| GET | `/api/alarms/<id>/clip` | 获取告警视频片段 | ✅ 已定义 |

#### 使用位置

- **AlarmHistory.vue** - 告警历史页面

#### 模拟数据使用情况

✅ **已使用模拟数据**

**文件位置：** `frontend/src/api/alarm.js`  
**模拟函数：** `alarmApiMock`  
**模拟数据：** 3条告警记录

```javascript
mockAlarms: [
  { id: 1, type: 'intrusion', severity: 'high', ... },
  { id: 2, type: 'crossing', severity: 'medium', ... },
  { id: 3, type: 'gathering', severity: 'low', ... }
]
```

#### 联调修改指南

**修改文件：** `frontend/src/views/AlarmHistory.vue`

需要修改的函数：
1. `loadAlarmList()` - 获取告警列表
2. `handleSubmitProcess()` - 处置告警

```javascript
// 示例：loadAlarmList函数
// ❌ 删除模拟API
// const response = await alarmApiMock.getList({...})

// ✅ 启用真实API
const response = await alarmApi.getList({...})
```

---

### I06 - IDashboard (大盘统计接口)

**负责人：** E  
**后端文件：** `backend/api/dashboard_api.py`  
**前端文件：** `frontend/src/api/dashboard.js`

#### 接口方法

| 方法 | 路径 | 说明 | 开发状态 |
|------|------|------|---------|
| GET | `/api/dashboard/summary` | 获取统计数据 | ✅ 已定义 |

#### 使用位置

- **Dashboard.vue** - 数据概览页面

#### 模拟数据使用情况

✅ **已使用模拟数据**

**文件位置：** `frontend/src/api/dashboard.js`  
**模拟函数：** `dashboardApiMock`

```javascript
async getSummary() {
  return {
    todayAlarms: 23,
    activeCameras: 18,
    recognizedFaces: 156,
    activeZones: 12,
    alarmTrend: [...],
    alarmTypeDistribution: [...]
  }
}
```

#### 联调修改指南

**修改文件：** `frontend/src/views/Dashboard.vue`

```javascript
// ❌ 删除模拟API
// const data = await dashboardApiMock.getSummary()

// ✅ 启用真实API
const data = await dashboardApi.getSummary()
```

---

## 🔄 统一修改方法

### 方法一：批量替换（推荐）

在项目根目录执行以下命令，批量替换所有模拟API调用：

```bash
# 查找所有使用模拟API的文件
grep -r "ApiMock" frontend/src/views/

# 手动替换每个文件中的模拟API调用
```

### 方法二：逐个修改

按照上述每个接口的"联调修改指南"，逐个修改对应文件。

### 方法三：环境变量控制（推荐）

可在 `frontend/src/api/request.js` 中添加环境变量控制：

```javascript
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// 在每个API文件中
export const faceApi = {
  getList(params) {
    if (USE_MOCK) {
      return faceApiMock.getList(params)
    }
    return request({ url: '/faces', method: 'GET', params })
  }
}
```

---

## ⚠️ 注意事项

1. **联调前准备**
   - 确认后端服务已启动（默认端口5000）
   - 确认所有接口路径与后端一致
   - 确认请求/响应数据格式与后端协商一致

2. **模拟数据删除**
   - 联调成功后，可删除所有 `xxxApiMock` 函数
   - 删除模拟数据数组（如 `mockFaces`, `mockAlarms` 等）

3. **错误处理**
   - 所有API调用都有 try-catch 错误处理
   - 联调时注意检查后端返回的错误码和错误信息

4. **Token处理**
   - 登录成功后token存储在 localStorage
   - request.js 已配置 Authorization header
   - 401错误会自动跳转登录页

---

## 📊 开发进度统计

| 项目 | 进度 |
|------|------|
| API接口封装 | 100% (6/6) |
| 页面开发 | 100% (5/5) |
| 模拟数据 | 100% (6/6) |
| 真实API对接 | 0% (待联调) |

---

## 📞 联调联系

- **IAuth/IUser/IFace** - 联系人员C
- **IZone** - 联系人员D
- **IAlarm/IDashboard** - 联系人员E

---

**最后更新时间：** 2026-07-07