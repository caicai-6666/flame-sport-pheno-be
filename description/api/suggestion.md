# 用户建议接口

## 接口概览

当前路由提供以下接口。

| 方法 | 路径 | 是否鉴权 | 说明 |
| --- | --- | ---: | --- |
| `POST` | `/flame/api/suggestion/remark` | 是 | 提交当前用户的建议 |

---

## POST `/flame/api/suggestion/remark`

请求示例：

```http
POST /flame/api/suggestion/remark
Authorization: auth_code
Content-Type: application/json
```

请求体：

```json
{
  "remark": "希望增加活动提醒功能"
}
```

请求字段：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `remark` | `string` | 是 | 建议内容；不能仅包含空白字符。 |

成功响应（`201 Created`）：

```json
{
  "id": 1,
  "created_at": "2026-08-06T10:00:00"
}
```

处理说明：

- 用户 ID 从 `Authorization` 中的登录态取得，不接受客户端传入的用户 ID。
- 建议内容去除首尾空白后写入 `user_suggestion.content`。
- 新建建议默认可见且处于待处理阶段，即 `status = 1`、`processing_stage = pending`。
- 赛季开始配置保护期内仍允许提交建议。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 400 | 建议内容仅为空白字符 | `建议内容不能为空` |
| 404 | 当前用户不存在 | `用户不存在` |
| 422 | 缺少 `remark` 或字段为空字符串 | 请求参数校验失败 |
