# 凭证接口

## 路由前缀

```text
/flame/api/proof
```

---

## 接口列表

当前路由提供以下接口。

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/flame/api/proof` | 否 | 凭证子路由存活校验 |
| `GET` | `/flame/api/proof/config` | 是 | 获取项目上传凭证配置 |
| `GET` | `/flame/api/proof/current` | 是 | 获取当前用户当前赛季凭证 |
| `GET` | `/flame/api/proof/history` | 是 | 获取当前用户过往赛季历史凭证 |
| `POST` | `/flame/api/proof/upload` | 是 | 上传或更新项目凭证 |

---

## GET `/flame/api/proof`

成功响应：

```json
{
  "code": 200
}
```

---

## GET `/flame/api/proof/config`

请求示例：

```http
GET /flame/api/proof/config?project_id=3
Authorization: auth_code
```

Query 参数：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `project_id` | `number` | 是 | 项目 ID，必须大于等于 1 |

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

---

## GET `/flame/api/proof/current`

该接口每次请求都从数据库查询当前激活赛季，并只返回该赛季的凭证。没有激活赛季时返回 `404`。

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
    "preliminaryReviewComment": "",
    "finalReviewComment": "",
    "note": "力量训练 45 分钟，包含深蹲、卧推和拉伸。",
    "imageName": "健身.webp",
    "imageUrl": "/flame/api/image/proof_record/18",
    "proofDate": "2026-07-19",
    "createdAt": "2026-07-19T15:30:00"
  }
]
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `seasonName` | `string` | 赛季名称，对应 `season.name` |
| `projectName` | `string` | 项目名称，对应 `project.name` |
| `reviewStatus` | `string` | 审核状态，取值见下方“审核状态取值” |
| `reviewComment` | `string` | 兼容字段，返回当前审核阶段的意见；待审核或未填写时返回空字符串 |
| `preliminaryReviewComment` | `string` | 大模型初审意见，对应 `preliminary_review_comment`；为空时返回空字符串 |
| `finalReviewComment` | `string` | 管理员终审意见，对应 `review_comment`；为空时返回空字符串 |
| `note` | `string` | 用户上传备注，对应 `proof_record.note`；为空时返回空字符串 |
| `imageName` | `string` | 凭证文件名，只保留 `{上传文件主名}.webp`，不带系统生成前缀 |
| `imageUrl` | `string` | 当前用户可读取的凭证图片地址；请求时仍需携带 `Authorization` |
| `proofDate` | `string` | 凭证对应的实际运动日期，对应 `proof_record.proof_date`，格式 `YYYY-MM-DD` |
| `createdAt` | `string` | 上传时间，对应 `proof_record.created_at` |

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
proof_record.proof_date DESC
proof_record.created_at DESC
proof_record.id DESC
```

---

## GET `/flame/api/proof/history`

该接口不依赖当前激活赛季，返回 `season.status IN (2, 3)` 的结算中或已结束赛季凭证。赛季离开进行中状态后即可进入客户端历史，便于用户查看结算期间的审核变化；`status = 0` 的未开始赛季和 `status = 1` 的当前激活赛季不会出现在历史记录中。

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
    "preliminaryReviewComment": "单次训练时长达标。",
    "finalReviewComment": "审核通过：健身凭证清晰，训练记录符合本项目打卡要求。",
    "imageName": "健身1.webp",
    "imageUrl": "/flame/api/image/proof_record/9",
    "proofDate": "2026-06-01",
    "createdAt": "2026-06-01T09:00:00"
  }
]
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `seasonName` | `string` | 赛季名称，对应 `season.name` |
| `projectName` | `string` | 项目名称，对应 `project.name` |
| `reviewStatus` | `string` | 审核状态，取值见下方“审核状态取值” |
| `reviewComment` | `string` | 当前审核阶段的意见；初审状态读取 `preliminary_review_comment`，终审状态读取 `review_comment`，待审核或为空时返回空字符串 |
| `preliminaryReviewComment` | `string` | 大模型初审意见；记录进入终审状态后仍保留，历史数据未保存时返回空字符串 |
| `finalReviewComment` | `string` | 管理员终审意见；尚未终审或未填写时返回空字符串 |
| `imageName` | `string` | 凭证文件名，只保留 `{上传文件主名}.webp`，不带系统生成前缀 |
| `imageUrl` | `string` | 当前用户可读取的凭证图片地址；请求时仍需携带 `Authorization` |
| `proofDate` | `string` | 凭证对应的实际运动日期，对应 `proof_record.proof_date`，格式 `YYYY-MM-DD` |
| `createdAt` | `string` | 上传时间，对应 `proof_record.created_at` |

数据来源：

```text
season_user.user_id = 当前登录用户 ID
season.status IN (2, 3)
proof_record.season_user_id = season_user.id
proof_record.project_id = project.id
season_user.season_id = season.id
proof_record.status = 1
```

排序：

```text
proof_record.proof_date DESC
proof_record.created_at DESC
proof_record.id DESC
```

文件名处理规则：

```text
bb123456-3-20260606090020-健身.webp -> 健身.webp
```

---

## POST `/flame/api/proof/upload`

请求类型：

```http
Content-Type: multipart/form-data
```

请求体：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `season_id` | `number` | 是 | 赛季 ID，必须大于等于 1 |
| `project_id` | `number` | 是 | 项目 ID，必须大于等于 1 |
| `project_upload_config_id` | `number` | 是 | 上传配置 ID，必须大于等于 1 |
| `record_type` | `string` | 否 | 兼容旧前端字段；传入时需和上传配置记录一致 |
| `proof_date` | `string` | 是 | 凭证对应的实际运动日期，格式 `YYYY-MM-DD` |
| `note` | `string` | 是 | 本次运动指标说明，供后续多模态初审使用 |
| `image` | `File` | 是 | JPEG、PNG 或 WebP 图片；服务端统一存储为 WebP |
| `image_segments` | `string` | 否 | 分段定位 JSON 字符串，省略或空白时保存为 SQL `NULL` |

### 图片分段定位

`image_segments` 通过 multipart 文本字段提交，UTF-8 编码最多 4096 字节。以下示例表示一张 1440 × 6000 像素图片中的两段原图区域：

```json
{
  "version": 1,
  "width": 1440,
  "height": 6000,
  "segments": [
    {"x": 16, "y": 16, "width": 1408, "height": 2800},
    {"x": 16, "y": 2832, "width": 1408, "height": 3152}
  ]
}
```

- 对象字段必须与示例一致，不接受额外字段；版本仅支持整数 `1`。
- 画布宽高必须是正整数，并与服务端修正 EXIF 方向、转换为 WebP 后的实际尺寸一致。
- `segments` 必须包含 1～5 个矩形；坐标为非负整数，宽高为正整数，不接受布尔值或小数。
- 矩形必须在画布内，按从上到下的顺序排列且纵向不能重叠；允许边距与间隙。

非法 JSON、尺寸不符、分段越界或其他定位校验失败返回 `400`，不创建本次图片目录或文件，也不更新凭证。省略字段或提交空白字符串兼容旧客户端，JSON 文本 `null` 不属于合法定位对象。同日期重传时定位随图片整体替换，未传定位会清空旧值。接口响应保持原有结构。

### 上传结果与业务校验

成功响应：

```json
{
  "created_at": "2026-07-19T15:30:00",
  "proof_date": "2026-07-19"
}
```

主要校验：

- 当前时间不能处于赛季开始配置保护期；保护期按 `Asia/Shanghai` 的 `season.start_date 00:00` 起算。
- 目标赛季必须处于激活状态，即 `season.status = 1`。
- 当前用户必须正式参与赛季，即 `season_user.level_id IS NOT NULL`。
- 当前用户必须锁定该项目，即存在有效 `season_user_project`。
- `project_upload_config_id` 必须属于当前 `project_id` 且启用。
- 如果传入 `record_type`，必须和上传配置中的 `record_type` 一致。
- `proof_date` 必须在目标赛季内，且不能晚于服务器当天；普通上传页面默认提交当天，补传页面提交用户选择的过去日期。
- `note` 必须填写非空内容，说明本次运动的可审核指标。
- 上传文件必须是可解码的 JPEG、PNG 或 WebP 且内容非空；服务端修正 EXIF 方向后，以质量 82 重编码并存储为 WebP。

如果前端提交已经隐藏或未激活的旧赛季 ID，接口会根据数据库中的实时状态拒绝上传，不会写入图片或凭证记录。

同运动日期重复上传规则：

```text
season_user_id + project_id + proof_date + status = 1
```

命中同项目同运动日期记录时覆盖：

```text
image_url
image_segments
note
project_upload_config_id
proof_date
created_at
review_status = pending
review_comment = NULL
preliminary_review_comment = NULL
```

重传后的 `pending` 表示待初审；此前的初审结果、当前审核意见和独立初审意见都会被清除。

响应中的 `reviewComment` 保持既有字段名，但按审核阶段选择来源：`preliminary_approved`、`preliminary_rejected` 返回 `preliminary_review_comment`；`approved`、`rejected` 返回终审专用的 `review_comment`；`pending` 返回空字符串。`preliminaryReviewComment` 和 `finalReviewComment` 则始终分别映射两个数据库字段，供客户端同时展示初审与终审意见。

重传时会先释放旧版本的实际进度贡献，并将空缺回补给同项目下尚未完全分配原始增量的其他有效通过凭证。重传记录的原始增量和实际贡献会清零；新版本初审通过后再从剩余进度空间中分配贡献。

---

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
| 400 | `proof_date` 晚于服务器当天 | `凭证日期不能晚于今天` |
| 400 | `proof_date` 不在赛季日期范围 | `凭证日期必须在赛季期间内` |
| 400 | 图片媒体类型不受支持 | `凭证图片仅支持 JPEG、PNG 或 WebP` |
| 400 | 图片内容无法解码或实际格式不受支持 | `上传内容不是有效的凭证图片` 或对应格式提示 |
| 400 | 上传图片为空 | `上传图片不能为空` |
| 409 | 用户尚未正式参与赛季 | `用户尚未正式参与该赛季` |
| 409 | 用户未锁定该项目 | `用户未锁定该项目` |
| 409 | 目标赛季未激活 | `赛季未激活，无法上传凭证` |
| 409 | 当前时间处于赛季开始配置保护期 | `赛季开始配置保护期内，暂不允许此操作` |
| 409 | 数据库同时存在多个激活赛季 | `存在多个激活赛季，无法判断用户写入保护期` |
| 404 | `season_id` 不存在 | `赛季不存在` |
| 422 | 必填字段缺失或数字字段小于 1 | FastAPI 参数校验错误 |
