# 用户接口

## 接口概览

| 方法 | 路径 | 是否鉴权 | 说明 |
| --- | --- | ---: | --- |
| GET | `/api/user` | 否 | 用户子路由存活校验 |
| POST | `/api/user/profile` | 是 | 设置当前用户资料 |

---

## GET /api/user

成功响应：

```json
{
  "code": 200
}
```

---

## POST /api/user/profile

请求示例：

```http
POST /api/user/profile
Authorization: auth_code
Content-Type: application/json
```

请求体：

```json
{
  "height_cm": 172.5
}
```

请求字段：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| height_cm | number | 是 | 用户身高，单位 cm，范围 50 到 300 |

成功响应：

```json
{
  "height_cm": 172.5
}
```

处理说明：

- 当前接口只更新 `user.height_cm`。
- 后端会将身高保留两位小数后写入数据库。
- 用户资料完整性检查仍通过 `/api/auth/profile_complete_check` 完成。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 400 | 身高超出范围 | `height_cm 必须在 50 到 300 之间` |
| 404 | 用户不存在 | `用户不存在` |
