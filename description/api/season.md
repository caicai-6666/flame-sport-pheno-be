# 赛季接口

## 路由前缀

```text
/flame/api/season
```

---

## 接口列表

当前路由提供以下接口。

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/flame/api/season` | 否 | 赛季子路由存活校验 |
| `GET` | `/flame/api/season/current` | 是 | 获取当前激活赛季 |
| `GET` | `/flame/api/season/participate_check` | 是 | 检查当前用户是否正式参与赛季 |

---

## GET `/flame/api/season`

成功响应：

```json
{
  "code": 200
}
```

---

## GET `/flame/api/season/current`

成功响应：

```json
{
  "season_id": 1,
  "name": "2026年7月赛季",
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "required_project_count": 3,
  "server_time": "2026-07-01T08:00:00+08:00",
  "user_write_frozen": true,
  "user_write_freeze_starts_at": "2026-07-01T00:00:00+08:00",
  "user_write_available_at": "2026-07-02T00:00:00+08:00"
}
```

配置保护期字段如下：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `server_time` | `string` | 上海时区的服务端响应时间，ISO 8601 格式 |
| `user_write_frozen` | `boolean` | 当前是否处于客户业务写入保护期 |
| `user_write_freeze_starts_at` | `string` | 保护期起点，ISO 8601 格式 |
| `user_write_available_at` | `string` | 恢复客户业务写入的时刻，ISO 8601 格式 |

上述字段供客户端展示只读状态和预计开放时间。客户端判断不替代 Service 事务内的写入保护校验；`ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS = 0` 时起止时刻相同，`user_write_frozen` 始终为 `false`。

数据来源：

```text
season.status = 1
ORDER BY season.start_date DESC
LIMIT 1
```

赛季状态含义：

| `status` | 含义 | 是否为当前赛季 |
| --- | --- | --- |
| `0` | 未开始 | 否 |
| `1` | 进行中 | 是 |
| `2` | 结算中 | 否 |
| `3` | 已结束 | 否 |

接口每次请求都直接查询数据库，不缓存当前赛季 ID 或要求锁定项目数量，因此后台调整激活状态后会立即反映到客户端。

确认当前赛季后，服务会确保 `assets/images/proof_record/{season_id}` 目录存在，为后续凭证上传预先准备本地存储位置。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 404 | 当前没有激活赛季 | `当前没有激活的赛季` |

---

## GET `/flame/api/season/participate_check`

请求示例：

```http
GET /flame/api/season/participate_check?season_id=1
Authorization: auth_code
```

成功响应：

```json
{
  "project_rule_level_id": 1
}
```

正式参与判断：

```text
season_user 存在
season_user.level_id IS NOT NULL
```

如果用户尚未正式参与，接口会按上海时区检查报名截止时间：今天与赛季开始日的日期差 `>= SEASON_PARTICIPATION_ALLOWED_DAYS` 时返回 `403`。默认 `7` 包含开始日当天，例如 9 月 1 日开始的赛季在 9 月 8 日 00:00 截止。提前激活但尚未开始的赛季允许抢先参与；已正式参与的用户仍正常返回等级。保护期与报名窗口的关系参见[报名时间与抢先参与](../business/season_project_flow.md#报名时间与抢先参与)。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 404 | 赛季不存在或未激活 | `赛季不存在或未激活` |
| 403 | 超过报名时间 | `已超过赛季报名时间` |
| 409 | 尚未正式参与 | `用户尚未正式参与该赛季` |
