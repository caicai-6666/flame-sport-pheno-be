# proof 接口文档

## 路由前缀

```text
/flame/api/proof
```

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/flame/api/proof` | 否 | 凭证子路由存活校验 |
| GET | `/flame/api/proof/config` | 是 | 获取项目上传凭证配置 |
| GET | `/flame/api/proof/current` | 是 | 获取当前用户当前赛季凭证 |
| GET | `/flame/api/proof/history` | 是 | 获取当前用户过往赛季历史凭证 |
| POST | `/flame/api/proof/upload` | 是 | 上传或更新项目凭证 |

## GET /flame/api/proof

成功响应：

```json
{
  "code": 200
}
```

## GET /flame/api/proof/config

请求示例：

```http
GET /flame/api/proof/config?project_id=3
Authorization: auth_code
```

Query 参数：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| project_id | number | 是 | 项目 ID，必须大于等于 1 |

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

如果项目没有启用的上传配置：

```json
{
  "uploadConfigs": []
}
```

数据来源：

```text
project_upload_config.project_id = project_id
project_upload_config.status = 1
ORDER BY sort_order ASC, id ASC
```

缓存策略：

```text
Cache-Control: private, max-age=300
```

后端会按 `project_id` 对上传配置做 5 分钟进程内缓存。上传配置属于低频变更数据，该缓存用于减少上传凭证窗口重复打开时的数据库查询；缓存过期后会重新读取 `project_upload_config`。

## GET /flame/api/proof/current

该接口只返回当前激活赛季的凭证。当前激活赛季 ID 来自服务内的 `CurrentSeasonRuntime`；如果运行时缓存未初始化，接口会先从当前激活赛季加载。

请求示例：

```http
GET /flame/api/proof/current
Authorization: auth_code
```

成功响应：

```json
[
  {
    "seasonName": "2026年7月赛季",
    "projectName": "健身",
    "reviewStatus": "pending",
    "reviewComment": "",
    "note": "力量训练 45 分钟，包含深蹲、卧推和拉伸。",
    "imageName": "健身.jpg",
    "createdAt": "2026-07-19T15:30:00"
  }
]
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| seasonName | string | 赛季名称，对应 `season.name` |
| projectName | string | 项目名称，对应 `project.name` |
| reviewStatus | string | 审核状态，取值见下方“审核状态取值” |
| reviewComment | string | 审核意见；初审任务后可返回通过依据或失败原因，未填写时返回空字符串 |
| note | string | 用户上传备注，对应 `proof_record.note`；为空时返回空字符串 |
| imageName | string | 凭证文件名，只保留 `{上传文件主名}.jpg`，不带系统生成前缀 |
| createdAt | string | 上传时间，对应 `proof_record.created_at` |

数据来源：

```text
season_user.user_id = 当前登录用户 ID
season_user.season_id = 当前激活赛季 ID
proof_record.season_user_id = season_user.id
proof_record.project_id = project.id
season_user.season_id = season.id
proof_record.status = 1
```

排序：

```text
proof_record.created_at DESC
proof_record.id DESC
```

## GET /flame/api/proof/history

该接口只返回过往赛季凭证，会排除当前激活赛季的上传记录。当前激活赛季 ID 来自服务内的 `CurrentSeasonRuntime`；如果运行时缓存未初始化，接口会先从当前激活赛季加载。

请求示例：

```http
GET /flame/api/proof/history
Authorization: auth_code
```

成功响应：

```json
[
  {
    "seasonName": "2026年6月赛季",
    "projectName": "健身",
    "reviewStatus": "approved",
    "reviewComment": "审核通过：健身凭证清晰，训练记录符合本项目打卡要求。",
    "imageName": "健身1.jpg",
    "createdAt": "2026-06-01T09:00:00"
  }
]
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| seasonName | string | 赛季名称，对应 `season.name` |
| projectName | string | 项目名称，对应 `project.name` |
| reviewStatus | string | 审核状态，取值见下方“审核状态取值” |
| reviewComment | string | 审核意见，对应 `proof_record.review_comment`；为空时返回空字符串 |
| imageName | string | 凭证文件名，只保留 `{上传文件主名}.jpg`，不带系统生成前缀 |
| createdAt | string | 上传时间，对应 `proof_record.created_at` |

数据来源：

```text
season_user.user_id = 当前登录用户 ID
season_user.season_id != 当前激活赛季 ID
proof_record.season_user_id = season_user.id
proof_record.project_id = project.id
season_user.season_id = season.id
proof_record.status = 1
```

排序：

```text
proof_record.created_at DESC
proof_record.id DESC
```

文件名处理规则：

```text
bb123456-3-20260606090020-健身.jpg -> 健身.jpg
```

## POST /flame/api/proof/upload

请求类型：

```http
Content-Type: multipart/form-data
```

请求体：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| season_id | number | 是 | 赛季 ID，必须大于等于 1 |
| project_id | number | 是 | 项目 ID，必须大于等于 1 |
| project_upload_config_id | number | 是 | 上传配置 ID，必须大于等于 1 |
| record_type | string | 否 | 兼容旧前端字段；传入时需和上传配置记录一致 |
| note | string | 是 | 本次运动指标说明，供后续文本初审使用 |
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
- 如果传入 `record_type`，必须和上传配置中的 `record_type` 一致。
- `note` 必须填写非空内容，说明本次运动的可审核指标。
- 上传文件必须是 JPG 且内容非空。

当天重复上传规则：

```text
season_user_id + project_id + project_upload_config_id + created_at 所在自然日 + status = 1
```

命中当天记录时覆盖：

```text
image_url
note
created_at
review_status = pending
review_comment = NULL
```

重传后的 `pending` 表示待初审；此前的初审结果和审核意见会被清除。

若当天同项目旧版本已初审通过，上传新版本时会先释放旧版本的实际进度贡献，并将空缺回补给同项目下尚未完全分配原始增量的其他有效通过凭证。重传记录的原始增量和实际贡献会清零；新版本初审通过后再从剩余进度空间中分配贡献。

## 审核状态取值

| 值 | 含义 |
| --- | --- |
| `pending` | 待初审 |
| `preliminary_approved` | 初审通过；可计入排行榜 |
| `preliminary_rejected` | 初审失败；用户可重新上传 |
| `approved` | 管理员终审通过；保留项目进度和排行榜资格 |
| `rejected` | 管理员终审失败；撤销项目进度且不计入后续排行榜快照 |

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 400 | 当前项目不支持上传配置 | `当前项目不支持该上传配置` |
| 400 | 上传配置和凭证类型不匹配 | `project_upload_config_id 与 record_type 不匹配` |
| 400 | `note` 超过 255 字符 | `note 长度不能超过 255` |
| 400 | `note` 为空或仅包含空白字符 | `note 不能为空，请填写本次运动指标` |
| 400 | 图片类型不是 JPG | `仅支持上传 JPG 图片` |
| 400 | 上传图片为空 | `上传图片不能为空` |
| 409 | 用户尚未正式参与赛季 | `用户尚未正式参与该赛季` |
| 409 | 用户未锁定该项目 | `用户未锁定该项目` |
| 422 | 必填字段缺失或数字字段小于 1 | FastAPI 参数校验错误 |
