# season 接口文档

## 路由前缀

```text
/flame/api/season
```

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/flame/api/season` | 否 | 赛季子路由存活校验 |
| GET | `/flame/api/season/current` | 是 | 获取当前激活赛季 |
| GET | `/flame/api/season/participate_check` | 是 | 检查当前用户是否正式参与赛季 |

## GET /flame/api/season

成功响应：

```json
{
  "code": 200
}
```

## GET /flame/api/season/current

成功响应：

```json
{
  "season_id": 1,
  "name": "2026年7月赛季",
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "required_project_count": 3
}
```

数据来源：

```text
season.status = 1
ORDER BY season.start_date DESC
LIMIT 1
```

接口会在当前进程内缓存当前赛季 ID 和要求锁定项目数量。

## GET /flame/api/season/participate_check

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

如果用户尚未正式参与，接口会继续判断是否超过允许参与天数。允许参与天数由配置项 `SEASON_PARTICIPATION_ALLOWED_DAYS` 控制。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 404 | 赛季不存在 | `赛季不存在` |
| 403 | 超过报名时间 | `已超过赛季报名时间` |
| 409 | 尚未正式参与 | `用户尚未正式参与该赛季` |
