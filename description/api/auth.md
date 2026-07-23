# auth 接口文档

## 路由前缀

```text
/flame/api/auth
```

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/flame/api/auth` | 否 | 鉴权子路由存活校验 |
| POST | `/flame/api/auth/login` | 否 | 登录并写入服务内存认证缓存 |
| GET | `/flame/api/auth/profile_complete_check` | 是 | 检查当前用户资料是否完整 |

## GET /flame/api/auth

用于确认 `auth` 子路由已注册。

成功响应：

```json
{
  "code": 200
}
```

## POST /flame/api/auth/login

请求体：

```json
{
  "auth_code": "钉钉客户端获取的免登授权码"
}
```

服务端会使用钉钉企业内部应用免登解析 `auth_code` 对应的 `userId`，并查询本地 `user`：

- 用户已存在且启用：直接登录。
- 用户不存在：继续查询钉钉员工详情和第一个所属部门的详情；钉钉姓名以空白字符切分，仅将首个片段写入本地 `user.name`；如有头像，下载并转换为 JPEG 后保存到本地头像目录，将 `/用户ID.jpg` 写入 `user.avatar_url`，再在一个事务中初始化本地 `department` 与 `user` 后登录。

成功后将：

```text
auth_code -> userId
```

写入进程内认证缓存，但响应仍返回原始 `auth_code`；前端应将其作为后续请求的 `Authorization` 值。

### 开发模式

当 `APP_MODE=development` 时，请求体和响应结构不变，但 `auth_code` 应直接填写数据库中已有的 `user.id`。服务端不会调用钉钉，而是按该 ID 查询本地启用用户；命中后缓存：

```text
auth_code -> user.id
```

由于开发约定下两者相同，缓存即为 `auth_code -> auth_code`。开发模式不创建用户、部门或头像。

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
| 404 | 开发模式中 `auth_code` 对应的本地用户不存在 | `开发登录用户不存在` |
| 401 | 钉钉免登授权码无效或过期 | `钉钉免登授权码无效或已过期` |
| 403 | 本地用户已停用，或首次初始化的所属部门已停用 | 对应停用提示 |
| 409 | 钉钉部门名称与本地部门数据冲突 | `钉钉部门名称与本地部门数据冲突` |
| 502 | 钉钉服务异常、资料缺失、通讯录权限不足或头像下载失败 | `钉钉登录服务暂时不可用，请稍后重试` |
| 503 | 未配置钉钉应用凭证 | `钉钉登录尚未完成服务端配置` |

## 后续访问鉴权

业务接口通过请求头传入：

```http
Authorization: auth_code
```

后端从认证缓存解析当前 `user_id`。缓存不存在、为空或过期时返回 `401`。

## GET /flame/api/auth/profile_complete_check

请求示例：

```http
GET /flame/api/auth/profile_complete_check
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
