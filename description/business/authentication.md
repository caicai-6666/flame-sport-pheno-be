# 鉴权业务说明

## 当前目标

当前阶段实现的是后端内部基础鉴权链路，用于支撑本地开发和前后端联调。

## 登录流程

```text
前端提交 auth_code
后端解析 user_id
查询 user 表
写入内存认证缓存
返回 auth_code
```

测试阶段的解析规则：

```text
auth_code = user_id
```

后续接入真实外部系统时，只需要替换 `AuthService._resolve_user_id_from_auth_code`。

## 访问受保护接口

前端在请求头传入：

```http
Authorization: auth_code
```

后端通过 `get_current_user_id` 从缓存中解析当前用户 ID。

## 用户资料完备性检查

当前资料完备性检查接口：

```text
GET /api/auth/profile_complete_check
```

当前阶段只检查 `user.height_cm` 是否已填写。

如果身高为空，返回：

```text
is_complete = false
missing_fields 包含 height_cm
```

后续如果需要强制补充更多用户资料，可以继续扩展该接口的检查字段。

## 认证缓存

缓存实现位于：

```text
app/core/api/auth_cache.py
```

缓存结构：

```text
auth_code -> user_id + expires_at
```

缓存采用滑动过期策略。用户在有效期内访问业务接口时，会刷新过期时间。

## 当前限制

- 缓存在单进程内存中，多实例部署时不会共享登录态。
- 暂未实现 refresh token。
- 暂未实现角色权限控制。
- 当前没有调用外部系统校验真实 `auth_code`。
