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
| GET | `/project/upload_config` | 是 | 获取项目上传配置 |
| POST | `/project/upload_proof` | 是 | 上传或更新项目凭证 |
| GET | `/project/lock_check` | 是 | 查询当前用户已锁定项目 |
| POST | `/project/lock` | 是 | 锁定赛季项目 |
| POST | `/project/lock_level` | 是 | 锁定赛季挑战等级 |

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

## GET /project/upload_config

请求示例：

```http
GET /project/upload_config?project_id=3
```

成功响应：

```json
{
  "uploadConfigs": [
    {
      "id": 3,
      "recordType": "普通凭证",
      "uploadHint": "训练照片、健身房打卡或课程记录",
      "noteExample": "例如：力量训练 45 分钟"
    }
  ]
}
```

数据来源：

```text
project_upload_config.project_id = project_id
project_upload_config.status = 1
ORDER BY sort_order ASC, id ASC
```

## POST /project/upload_proof

请求类型：

```http
Content-Type: multipart/form-data
```

请求体：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| season_id | number | 是 | 赛季 ID |
| project_id | number | 是 | 项目 ID |
| project_upload_config_id | number | 是 | 上传配置 ID |
| record_type | string | 否 | 兼容旧前端字段；传入时需和上传配置记录一致 |
| note | string | 否 | 用户备注 |
| image | File | 是 | JPG 图片 |

成功响应：

```json
{
  "created_at": "2026-07-19T15:30:00"
}
```

主要校验：

- 当前用户必须正式参与赛季，即 `season_user.level_id IS NOT NULL`。
- 当前用户必须锁定该项目，即存在有效 `season_user_project`。
- `project_upload_config_id` 必须属于当前 `project_id` 且启用。
- 上传文件必须是 JPG 且内容非空。

当天重复上传规则：

```text
season_user_id + project_id + project_upload_config_id + created_at 所在自然日 + status = 1
```

命中当天记录时覆盖 `image_url`、`note`、`created_at`，并将审核状态重置为 `pending`。

## GET /project/lock_check

请求示例：

```http
GET /project/lock_check?season_id=1
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
