# 鉴权业务说明

## 当前目标

后端通过 `APP_MODE` 切换登录身份解析方式，最终都写入同一份认证缓存。

| `APP_MODE` | 登录方式 |
| --- | --- |
| `production`（默认） | 钉钉企业内部 H5 微应用免登 |
| `development` | 将前端提交的 `auth_code` 直接作为本地 `user.id` 查询 |

---

## 登录流程

```text
生产模式前端提交 auth_code
  -> 获取有效钉钉应用 access token
  -> 使用 access token 和 auth_code 向钉钉请求 userId
  -> 查询本地 user
      -> 已存在且启用：写入认证缓存
      -> 不存在：查询钉钉用户详情和所属部门详情
                 -> 在同一事务中创建 department 与 user
                 -> 写入认证缓存
  -> 返回原 auth_code
```

钉钉 `userId` 直接作为系统 `user.id` 使用。登录成功后，响应体仍返回原始 `auth_code`，供前端继续作为 `Authorization` 请求头；服务端缓存保存的映射则是：

```text
auth_code -> userId
```

因此业务接口能够通过 `auth_code` 找到本地用户主键，而不会把一次性免登码误用为用户 ID。

---

## 开发模式登录

开发模式不调用钉钉，也不会初始化钉钉 access token 定时刷新任务。前端仍调用原有接口并提交：

```json
{
  "auth_code": "本地 user.id"
}
```

服务端仅查询启用的本地用户；命中后直接写入：

```text
auth_code -> user.id
```

当前开发约定中两者值相同，因此缓存表现为 `auth_code -> auth_code`。用户不存在返回 `404`，用户停用返回 `403`；开发模式不会创建用户或同步部门、头像。

---

## 首次登录初始化

本地不存在 `user` 时，服务端使用同一个钉钉应用 access token 继续查询：

1. 员工详情：获取 `userId`、`name`、`avatar` 和 `dept_id_list`。姓名按空白字符切分后仅保留第一个片段作为本地 `user.name`；例如钉钉返回 `James 蔡昌言` 时本地保存并展示 `James`。
2. 员工部门列表的第一个部门详情：同步部门 ID 和名称。
3. 若钉钉返回头像地址，下载 JPEG、PNG 或 WebP 图片并统一转换、压缩为不超过 300 KiB 的 WebP 后保存到本地 `assets/images/avatar/`；文件名使用安全化后的 `userId` 加小写 `.webp`，例如 `james.webp`，`user.avatar_url` 保存为 `/james.webp`。
4. 在一个数据库事务中创建不存在的 `department` 与 `user`，随后才写入认证缓存。数据库初始化失败时会恢复本次覆盖前的头像文件。

当前 `user` 表只有一个 `department_id`，所以暂时将钉钉 `dept_id_list` 的第一个部门作为平台归属部门。用户、部门或部门名唯一约束发生并发冲突时，事务会回滚；若是同一用户的并发首次登录已被另一请求创建，则回读该用户并继续登录。

本地已存在但 `status = 0` 的用户会被拒绝，不会由钉钉同步自动重新启用；首次初始化遇到已停用的本地部门也会拒绝登录。

生产部署前需要在钉钉应用权限中开通员工信息和部门信息的读取权限；免登接口只能确认身份，首次初始化的两次详情查询还依赖这些通讯录权限。

钉钉头像下载仅接受 HTTP(S) 地址、JPEG/PNG/WebP 格式和 5 MiB 以内的文件。保存前会修正 EXIF 方向并统一转换为真实 WebP 字节，带透明通道的源图继续保留透明效果。编码时优先降低 WebP 质量、必要时缩小尺寸，使最终文件不超过 300 KiB；用户头像后缀统一为小写 `.webp`。WebP 编码在线程池执行，避免首次登录阻塞其他异步请求。

现有用户头像已按同一规则迁移为 WebP，`user.avatar_url` 统一使用 `.webp` 地址。钉钉没有头像时允许用户以空头像完成初始化；头像地址存在但无法下载、无法转换、压缩后仍无法满足大小限制或格式不合规时，初始化失败且不会创建用户。

---

## 钉钉应用 access token

```text
app/core/dingtalk.py
```

`DINGTALK_CLIENT_ID` 和 `DINGTALK_CLIENT_SECRET` 从环境变量读取。应用启动后会定时预热 token；登录请求在 token 临近过期时还会加锁刷新，避免定时任务偶发失败导致登录不可用。

---

## 访问受保护接口

前端在请求头传入：

```http
Authorization: auth_code
```

后端通过 `get_current_user_id` 从缓存中解析当前用户 ID。

---

## 用户资料完备性检查

当前资料完备性检查接口：

```text
GET /flame/api/auth/profile_complete_check
```

当前阶段只检查 `user.height_cm` 是否已填写。

如果身高为空，返回：

```text
is_complete = false
missing_fields 包含 height_cm
```

后续如果需要强制补充更多用户资料，可以继续扩展该接口的检查字段。

---

## 认证缓存

认证缓存实现位于：

```text
app/core/auth_cache.py
```

缓存结构：

```text
auth_code -> user_id + expires_at
```

缓存采用滑动过期策略。用户在有效期内访问业务接口时，会刷新过期时间。

---

## 当前限制

- 缓存在单进程内存中，多实例部署时不会共享登录态。
- 钉钉应用 access token 同样是进程内缓存；多实例部署时应迁移到 Redis 等共享缓存。
- 暂未实现 refresh token。
- 暂未实现角色权限控制。
- 为兼容现有前端，成功登录后仍将原始 `auth_code` 作为后续 `Authorization` 值；生产环境建议后续替换为后端生成的随机会话 token。
