# auth 接口文档

## 路由前缀

```text
/api/auth
```

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/auth` | 否 | 鉴权子路由存活校验 |
| POST | `/api/auth/login` | 否 | 登录并写入服务内存认证缓存 |
| GET | `/api/auth/profile_complete_check` | 是 | 检查当前用户资料是否完整 |

## GET /api/auth

用于确认 `auth` 子路由已注册。

成功响应：

```json
{
  "code": 200
}
```

## POST /api/auth/login

请求体：

```json
{
  "auth_code": "bb123456"
}
```

当前测试阶段，后端将 `auth_code` 直接视为 `user_id`，查询 `user` 表确认用户存在后，将：

```text
auth_code -> user_id
```

写入进程内认证缓存。

成功响应：

```json
{
  "auth_code": "bb123456"
}
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 400 | `auth_code` 为空 | `auth_code 不能为空` |
| 401 | 用户不存在或不可登录 | `用户不存在或无权限登录` |

## 后续访问鉴权

业务接口通过请求头传入：

```http
Authorization: auth_code
```

后端从认证缓存解析当前 `user_id`。缓存不存在、为空或过期时返回 `401`。

## GET /api/auth/profile_complete_check

请求示例：

```http
GET /api/auth/profile_complete_check
Authorization: auth_code
```

当前阶段只检查 `user.height_cm` 是否已填写。

成功响应：

```json
{
  "is_complete": false,
  "height_cm_completed": false,
  "missing_fields": ["height_cm"]
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| is_complete | boolean | 当前用户资料是否完整 |
| height_cm_completed | boolean | 身高字段是否已填写 |
| missing_fields | array | 当前缺失字段列表 |

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 404 | 用户不存在 | `用户不存在` |
