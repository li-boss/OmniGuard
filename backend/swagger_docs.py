"""OpenAPI metadata for the existing OmniGuard HTTP API.

This module is documentation-only. It deliberately describes the current
routes without wrapping views or changing request/response handling.
"""


SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "openapi",
            "route": "/apispec_1.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}


SECURITY = [{"BearerAuth": []}]
JSON_RESPONSE = {
    "type": "object",
    "properties": {
        "code": {"type": "integer", "example": 0},
        "message": {"type": "string", "example": "ok"},
        "data": {"type": "object"},
    },
}
ERROR_RESPONSE = {
    "type": "object",
    "properties": {
        "code": {"type": "integer", "example": 1},
        "message": {"type": "string", "example": "请求失败"},
        "data": {"type": "object", "nullable": True, "example": None},
    },
}


def json_body(properties, required):
    return {
        "in": "body",
        "name": "body",
        "required": True,
        "schema": {
            "type": "object",
            "required": required,
            "properties": properties,
        },
    }


def response(description, schema=JSON_RESPONSE):
    return {"description": description, "schema": schema}


SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "OmniGuard API",
        "description": "校园智能安防系统接口文档",
        "version": "1.0.0",
    },
    "basePath": "/",
    "schemes": ["http"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "securityDefinitions": {
        "BearerAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "输入 Bearer token，例如：Bearer eyJ...",
        }
    },
    "tags": [
        {"name": "认证", "description": "用户注册、登录与令牌刷新"},
        {"name": "用户", "description": "当前用户信息与密码管理"},
        {"name": "人脸", "description": "人脸注册、查询和删除"},
        {"name": "通行日志", "description": "人员通行记录查询、详情和删除"},
        {"name": "告警", "description": "告警查询、详情、录像和删除"},
        {"name": "视频流", "description": "实时 MJPEG 视频流"},
    ],
    "paths": {
        "/api/auth/register": {
            "post": {
                "tags": ["认证"],
                "summary": "注册用户",
                "parameters": [json_body({
                    "username": {"type": "string", "example": "operator01"},
                    "password": {"type": "string", "format": "password", "example": "password123"},
                    "role": {"type": "string", "default": "operator", "example": "operator"},
                }, ["username", "password"])],
                "responses": {
                    "201": response("注册成功"),
                    "409": response("用户名已存在", ERROR_RESPONSE),
                },
            }
        },
        "/api/auth/login": {
            "post": {
                "tags": ["认证"],
                "summary": "用户登录",
                "parameters": [json_body({
                    "username": {"type": "string", "example": "admin"},
                    "password": {"type": "string", "format": "password", "example": "admin123"},
                }, ["username", "password"])],
                "responses": {
                    "200": {
                        "description": "登录成功，data.token 为 JWT",
                        "schema": JSON_RESPONSE,
                        "examples": {"application/json": {
                            "code": 0,
                            "message": "登录成功",
                            "data": {"token": "<JWT>", "user": {"id": 1, "username": "admin", "role": "admin"}},
                        }},
                    },
                    "401": response("用户名或密码错误", ERROR_RESPONSE),
                },
            }
        },
        "/api/auth/refresh": {
            "post": {
                "tags": ["认证"],
                "summary": "刷新访问令牌",
                "security": SECURITY,
                "responses": {
                    "200": response("返回新的 data.token"),
                    "401": response("缺少或已过期的令牌", ERROR_RESPONSE),
                    "422": response("令牌格式无效", ERROR_RESPONSE),
                },
            }
        },
        "/api/users/me": {
            "get": {
                "tags": ["用户"],
                "summary": "查询当前用户",
                "security": SECURITY,
                "responses": {
                    "200": response("当前用户信息"),
                    "401": response("未认证", ERROR_RESPONSE),
                    "404": response("用户不存在", ERROR_RESPONSE),
                },
            }
        },
        "/api/users/me/password": {
            "put": {
                "tags": ["用户"],
                "summary": "修改当前用户密码",
                "security": SECURITY,
                "parameters": [json_body({
                    "oldPassword": {"type": "string", "format": "password"},
                    "newPassword": {"type": "string", "format": "password", "minLength": 6},
                }, ["oldPassword", "newPassword"])],
                "responses": {
                    "200": response("密码修改成功"),
                    "400": response("旧密码错误或新密码过短", ERROR_RESPONSE),
                    "401": response("未认证", ERROR_RESPONSE),
                },
            }
        },
        "/api/faces/register": {
            "post": {
                "tags": ["人脸"],
                "summary": "注册人脸",
                "description": "管理员/安全员可为任意用户注册；普通用户只能为自己注册。image 为 Base64 图片或 data URL。",
                "security": SECURITY,
                "parameters": [json_body({
                    "studentId": {"type": "string", "example": "20210001"},
                    "name": {"type": "string", "example": "张三"},
                    "image": {"type": "string", "example": "data:image/jpeg;base64,<BASE64>"},
                    "device_code": {"type": "string", "example": "cam-1"},
                }, ["studentId", "name", "image"])],
                "responses": {
                    "201": response("人脸注册成功"),
                    "400": response("参数、图片或人脸检测失败", ERROR_RESPONSE),
                    "401": response("未认证", ERROR_RESPONSE),
                    "403": response("权限不足", ERROR_RESPONSE),
                    "500": response("图片或数据库保存失败", ERROR_RESPONSE),
                },
            }
        },
        "/api/faces": {
            "get": {
                "tags": ["人脸"],
                "summary": "查询人脸列表",
                "description": "普通用户只能查询自己的人脸。",
                "security": SECURITY,
                "parameters": [{"in": "query", "name": "user_id", "type": "integer", "required": False}],
                "responses": {
                    "200": response("人脸列表"),
                    "401": response("未认证", ERROR_RESPONSE),
                },
            }
        },
        "/api/faces/{face_id}": {
            "delete": {
                "tags": ["人脸"],
                "summary": "删除人脸",
                "security": SECURITY,
                "parameters": [{"in": "path", "name": "face_id", "type": "integer", "required": True}],
                "responses": {
                    "200": response("删除成功"),
                    "401": response("未认证", ERROR_RESPONSE),
                    "403": response("权限不足", ERROR_RESPONSE),
                    "404": response("人脸不存在", ERROR_RESPONSE),
                    "500": response("数据库删除失败", ERROR_RESPONSE),
                },
            }
        },
        "/api/access-logs": {
            "get": {
                "tags": ["通行日志"],
                "summary": "分页查询通行日志",
                "description": "普通用户只能查询自己的记录；管理员和安保人员可以查询全部记录。",
                "security": SECURITY,
                "parameters": [
                    {"in": "query", "name": "page", "type": "integer", "default": 1},
                    {"in": "query", "name": "pageSize", "type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    {"in": "query", "name": "user_id", "type": "integer"},
                    {"in": "query", "name": "zone_id", "type": "integer"},
                    {"in": "query", "name": "access_method", "type": "string", "example": "face"},
                    {"in": "query", "name": "result", "type": "string", "example": "granted"},
                    {"in": "query", "name": "device_code", "type": "string", "example": "cam-1"},
                    {"in": "query", "name": "start_time", "type": "string", "format": "date-time"},
                    {"in": "query", "name": "end_time", "type": "string", "format": "date-time"},
                ],
                "responses": {
                    "200": response("通行日志分页数据，data 包含 items、total、page、pageSize 和 pages"),
                    "401": response("未认证", ERROR_RESPONSE),
                    "403": response("普通用户尝试查询其他用户记录", ERROR_RESPONSE),
                },
            }
        },
        "/api/access-logs/{log_id}": {
            "get": {
                "tags": ["通行日志"],
                "summary": "查询通行日志详情",
                "description": "普通用户只能查看自己的记录；管理员和安保人员可以查看全部记录。",
                "security": SECURITY,
                "parameters": [{"in": "path", "name": "log_id", "type": "integer", "required": True}],
                "responses": {
                    "200": response("通行日志详情"),
                    "401": response("未认证", ERROR_RESPONSE),
                    "403": response("权限不足", ERROR_RESPONSE),
                    "404": response("通行日志不存在", ERROR_RESPONSE),
                },
            },
            "delete": {
                "tags": ["通行日志"],
                "summary": "删除通行日志",
                "description": "仅管理员和安保人员可以删除通行日志。",
                "security": SECURITY,
                "parameters": [{"in": "path", "name": "log_id", "type": "integer", "required": True}],
                "responses": {
                    "200": response("删除成功"),
                    "401": response("未认证", ERROR_RESPONSE),
                    "403": response("权限不足", ERROR_RESPONSE),
                    "404": response("通行日志不存在", ERROR_RESPONSE),
                },
            },
        },
        "/api/alarms": {
            "get": {
                "tags": ["告警"],
                "summary": "分页查询告警",
                "security": SECURITY,
                "parameters": [
                    {"in": "query", "name": "page", "type": "integer", "default": 1},
                    {"in": "query", "name": "per_page", "type": "integer", "default": 10},
                    {"in": "query", "name": "pageSize", "type": "integer", "description": "per_page 的兼容参数"},
                    {"in": "query", "name": "type", "type": "string"},
                    {"in": "query", "name": "severity", "type": "string"},
                    {"in": "query", "name": "status", "type": "string"},
                    {"in": "query", "name": "camera_id", "type": "string"},
                    {"in": "query", "name": "start_time", "type": "string", "format": "date-time"},
                    {"in": "query", "name": "end_time", "type": "string", "format": "date-time"},
                ],
                "responses": {
                    "200": response("告警分页数据，data 包含 items、total、page、per_page、pages"),
                    "401": response("未认证", ERROR_RESPONSE),
                },
            }
        },
        "/api/alarms/{alarm_id}": {
            "get": {
                "tags": ["告警"],
                "summary": "查询告警详情",
                "security": SECURITY,
                "parameters": [{"in": "path", "name": "alarm_id", "type": "integer", "required": True}],
                "responses": {
                    "200": response("告警详情"),
                    "401": response("未认证", ERROR_RESPONSE),
                    "404": response("告警不存在", ERROR_RESPONSE),
                },
            },
            "delete": {
                "tags": ["告警"],
                "summary": "删除告警及关联媒体文件",
                "security": SECURITY,
                "parameters": [{"in": "path", "name": "alarm_id", "type": "integer", "required": True}],
                "responses": {
                    "200": response("删除成功"),
                    "401": response("未认证", ERROR_RESPONSE),
                    "404": response("告警不存在", ERROR_RESPONSE),
                },
            },
        },
        "/api/alarms/{alarm_id}/video": {
            "get": {
                "tags": ["告警"],
                "summary": "回放告警录像",
                "description": "返回 video/mp4，支持 HTTP Range/conditional 请求。",
                "produces": ["video/mp4", "application/json"],
                "security": SECURITY,
                "parameters": [{"in": "path", "name": "alarm_id", "type": "integer", "required": True}],
                "responses": {
                    "200": {"description": "MP4 视频流", "schema": {"type": "file"}},
                    "401": response("未认证", ERROR_RESPONSE),
                    "404": response("告警、录像路径或文件不存在", ERROR_RESPONSE),
                },
            }
        },
        "/api/streams/{camera_id}.mjpg": {
            "get": {
                "tags": ["视频流"],
                "summary": "获取摄像头实时 MJPEG 流",
                "description": "长连接响应，Content-Type 为 multipart/x-mixed-replace; boundary=frame。",
                "produces": ["multipart/x-mixed-replace"],
                "parameters": [{"in": "path", "name": "camera_id", "type": "string", "required": True, "example": "cam-1"}],
                "responses": {
                    "200": {"description": "实时 MJPEG 视频流", "schema": {"type": "string", "format": "binary"}},
                },
            }
        },
    },
}
