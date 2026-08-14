# 项目接口

## 路由前缀

```text
/flame/api/project
```

---

## 接口列表

当前路由提供以下接口。

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/flame/api/project` | 否 | 项目子路由存活校验 |
| `GET` | `/flame/api/project/list` | 是 | 获取启用项目列表 |
| `GET` | `/flame/api/project/rules` | 是 | 获取项目挑战规则 |
| `GET` | `/flame/api/project/lock_check` | 是 | 查询当前用户已锁定项目 |
| `GET` | `/flame/api/project/progress` | 是 | 查询已锁定项目的赛季完成进度 |
| `POST` | `/flame/api/project/lock` | 是 | 锁定赛季项目 |
| `POST` | `/flame/api/project/lock_level` | 是 | 锁定赛季挑战等级 |

凭证上传配置和凭证上传已迁移到 `proof` 路由：

```text
GET /flame/api/proof/config
POST /flame/api/proof/upload
```

---

## GET `/flame/api/project`

成功响应：

```json
{
  "code": 200
}
```

---

## GET `/flame/api/project/list`

成功响应：

```json
[
  {
    "project_id": 1,
    "name": "步行",
    "description": "把日常运动转化为稳定积分。",
    "image": "/日常步数.webp"
  }
]
```

数据来源：

```text
project.status = 1
ORDER BY project.id ASC
```

`image` 直接返回 `project.icon_url` 保存的项目图标相对地址，例如 `/日常步数.webp`。项目图标统一使用无损 WebP，以保留透明边缘并减小传输体积。前端获取图标时应请求：

```text
GET /flame/api/image/project_icon?filename={encodeURIComponent(image)}
```

---

## GET `/flame/api/project/rules`

请求示例：

```http
GET /flame/api/project/rules?project_id=1
Authorization: auth_code
```

成功响应：

```json
[
  {
    "project_rule_level_id": 1,
    "name": "青铜挑战",
    "reward": 100,
    "sub_desc": "建立稳定习惯",
    "rule_content": [
      {
        "label": "累计次数",
        "value": "15次"
      }
    ],
    "rule_note": "按自然日统计"
  }
]
```

数据来源：

```text
project_rule.project_id = project_id
project_rule.status = 1
project_level.status = 1
project_rule.level_id = project_level.id
```

---

## GET `/flame/api/project/lock_check`

请求示例：

```http
GET /flame/api/project/lock_check?season_id=1
Authorization: auth_code
```

成功响应：

```json
[
  1,
  3,
  5
]
```

如果没有 `season_user` 记录，返回空数组。

接口只接受数据库当前激活赛季的 `season_id`。没有激活赛季时返回 `404`；传入未开始、结算中或已结束赛季 ID 时返回 `400`。

---

## GET `/flame/api/project/progress`

请求示例：

```http
GET /flame/api/project/progress?season_id=1
Authorization: auth_code
```

成功响应：

```json
[
  {
    "project_id": 1,
    "completion_progress": 0.35
  }
]
```

仅返回当前用户在指定赛季已锁定且有效的项目。`completion_progress` 为 `0`～`1` 的数值；新锁定项目初始值为 `0`，后续定时初审通过后累积更新。

接口只接受数据库当前激活赛季的 `season_id`。没有激活赛季时返回 `404`；传入未开始、结算中或已结束赛季 ID 时返回 `400`。

---

## POST `/flame/api/project/lock`

请求体：

```json
{
  "season_id": 1,
  "project_id": 3
}
```

成功响应：

```json
{
  "code": 200
}
```

接口只允许锁定当前激活赛季下启用的项目，最多锁定数量由 `season.required_project_count` 控制。

每次请求都会直接查询数据库激活赛季，不使用进程内赛季缓存。

---

## POST `/flame/api/project/lock_level`

请求体：

```json
{
  "season_id": 1,
  "project_rule_level_id": 2
}
```

成功响应：

```json
{
  "code": 200
}
```

用户必须先锁满当前赛季要求数量的项目，且当前赛季尚未锁定等级。

成功锁定等级即视为正式报名，服务会在同一事务中写入 `season_user.participated_at`。

每次请求都会直接查询数据库激活赛季；没有激活赛季时返回 `404`，请求中的 `season_id` 不是当前激活赛季时返回 `400`。
