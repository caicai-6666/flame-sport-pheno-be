# project 接口文档

## 路由前缀

```text
/project
```

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/project` | 否 | 项目子路由存活校验 |
| GET | `/project/list` | 是 | 获取启用项目列表 |
| GET | `/project/rules` | 是 | 获取项目挑战规则 |
| GET | `/project/lock_check` | 是 | 查询当前用户已锁定项目 |
| POST | `/project/lock` | 是 | 锁定赛季项目 |
| POST | `/project/lock_level` | 是 | 锁定赛季挑战等级 |

凭证上传配置和凭证上传已迁移到 `proof` 路由：

```text
GET /proof/config
POST /proof/upload
```

## GET /project

成功响应：

```json
{
  "code": 200
}
```

## GET /project/list

成功响应：

```json
[
  {
    "project_id": 1,
    "name": "步行",
    "description": "把日常运动转化为稳定积分。",
    "image": "base64字符串"
  }
]
```

数据来源：

```text
project.status = 1
ORDER BY project.id ASC
```

`image` 由 `project.icon_url` 对应的本地项目图标读取后转为 base64。

## GET /project/rules

请求示例：

```http
GET /project/rules?project_id=1
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

## GET /project/lock_check

请求示例：

```http
GET /project/lock_check?season_id=1
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

## POST /project/lock

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

## POST /project/lock_level

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
