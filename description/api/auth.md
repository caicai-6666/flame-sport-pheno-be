# auth 接口文档

## 路由前缀

```text
/auth
```

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/auth` | 否 | 鉴权子路由存活校验 |
| POST | `/auth/login` | 否 | 登录并写入服务内存认证缓存 |

## GET /auth

用于确认 `auth` 子路由已注册。

成功响应：

```json
{
  "code": 200
}
```

## POST /auth/login

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
