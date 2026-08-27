# 补传接口

## 路由前缀

```text
/flame/api/supplement
```

---

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/flame/api/supplement/records` | 是 | 查询当前用户可以补传的结算中赛季凭证 |
| `POST` | `/flame/api/supplement/upload` | 是 | 补交一条已开放资格的结算中赛季凭证 |

---

## GET `/flame/api/supplement/records`

根据当前登录用户查询结算中赛季仍然开放的补传资格，并返回对应原凭证的展示信息。接口只提供查询，不会修改补传资格、审核状态或项目进度。

请求示例：

```http
GET /flame/api/supplement/records
Authorization: auth_code
```

查询条件：

```text
season_user.user_id = 当前登录用户 ID
season.status = 2
season_supplement_eligibility.status = 1
proof_record.status = 1
project.status = 1
season_supplement_eligibility.season_user_id = season_user.id
season_supplement_eligibility.proof_record_id = proof_record.id
proof_record.season_user_id = season_user.id
```

成功响应：

```json
[
  {
    "seasonId": 6,
    "seasonUserId": 79,
    "proofRecordId": 295,
    "seasonName": "2026年7月赛季",
    "projectName": "跑步",
    "reviewStatus": "rejected",
    "reviewComment": "凭证信息未达到终审要求。",
    "preliminaryReviewComment": "本次距离和配速均达标。",
    "finalReviewComment": "凭证信息未达到终审要求。",
    "note": "完成跑步5公里",
    "imageName": "跑步.webp",
    "imageUrl": "/flame/api/image/proof_record/295",
    "proofDate": "2026-07-18",
    "createdAt": "2026-07-18T08:30:00"
  }
]
```

响应字段如下：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `seasonId` | `integer` | 结算中赛季 ID |
| `seasonUserId` | `integer` | 当前用户对应的赛季参与记录 ID |
| `proofRecordId` | `integer` | 获得补传资格的原凭证记录 ID |
| `seasonName` | `string` | 赛季名称 |
| `projectName` | `string` | 运动项目名称 |
| `reviewStatus` | `string` | 原凭证当前审核状态 |
| `reviewComment` | `string` | 原凭证当前审核阶段的意见；初审状态读取 `preliminary_review_comment`，终审状态读取 `review_comment`，待审核或为空时返回空字符串 |
| `preliminaryReviewComment` | `string` | 原凭证的大模型初审意见；未保存时返回空字符串 |
| `finalReviewComment` | `string` | 原凭证的管理员终审意见；未终审或未填写时返回空字符串 |
| `note` | `string` | 用户原凭证备注；为空时返回空字符串 |
| `imageName` | `string` | 去除系统前缀后的凭证文件名 |
| `imageUrl` | `string` | 当前用户可读取的凭证图片地址 |
| `proofDate` | `string` | 凭证实际运动日期，格式为 `YYYY-MM-DD` |
| `createdAt` | `string` | 凭证上传时间，精确到秒 |

排序规则：

```text
season.start_date DESC
proof_record.proof_date DESC
proof_record.created_at DESC
proof_record.id DESC
```

当前用户没有开放的补传资格时返回空数组：

```json
[]
```

错误响应：

| 状态码 | 场景 | `detail` |
| --- | --- | --- |
| `401` | 未登录或登录状态失效 | `登录状态无效或已过期，请重新登录` |

> **注意**
>
> `imageUrl` 仍需要携带当前登录态访问。接口会同时校验资格归属和原凭证归属，不能通过其他用户的资格 ID 或凭证 ID 读取记录。

---

## POST `/flame/api/supplement/upload`

补交资格表中指定 `proof_record_id` 对应的原凭证。请求主体与普通凭证上传一致，并额外提交原凭证 ID；后端只会原位覆盖该记录，不会新建凭证或按日期覆盖其他记录。

请求类型：

```http
Content-Type: multipart/form-data
```

请求体：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `proof_record_id` | `number` | 是 | 获得补传资格的原凭证记录 ID，必须大于等于 1 |
| `season_id` | `number` | 是 | 原凭证所属结算中赛季 ID，必须大于等于 1 |
| `project_id` | `number` | 是 | 原凭证所属项目 ID，必须大于等于 1 |
| `project_upload_config_id` | `number` | 是 | 本次补交使用的启用上传配置 ID，必须属于原项目 |
| `record_type` | `string` | 否 | 兼容旧前端字段；传入时必须与上传配置一致 |
| `proof_date` | `string` | 是 | 原凭证运动日期，格式为 `YYYY-MM-DD`，补交时不允许改动 |
| `note` | `string` | 是 | 本次补交的运动指标说明 |
| `image` | `File` | 是 | JPEG、PNG 或 WebP 图片；服务端统一保存为 WebP |

成功响应：

```json
{
  "created_at": "2026-08-18T16:20:00",
  "proof_date": "2026-07-18"
}
```

主要校验：

- 当前时间不能处于新激活赛季开始后的客户写入保护期。
- `season_supplement_eligibility.proof_record_id` 必须等于请求中的 `proof_record_id`，且资格状态为 `1`。
- 资格和凭证必须属于当前登录用户，凭证及项目必须可见，所属赛季必须仍处于结算中。
- 请求中的 `season_id`、`project_id` 和 `proof_date` 必须与资格绑定的原凭证一致。
- 当前赛季用户必须仍保留该项目的有效锁定记录。
- 上传配置、备注和图片校验与普通凭证上传接口一致。

成功补交后，系统在同一事务内执行以下变更：

```text
原 proof_record 原位更新图片、备注、上传配置和上传时间
review_status = pending
review_comment = NULL
progress_delta = 0
increase = 0
season_supplement_eligibility.status = 0
```

旧凭证此前占用的项目进度会先释放并尝试回补给同项目其他有效通过凭证。数据库提交失败时，新图片会被清理且资格保持开放；提交成功后才清理旧图片。

错误响应：

| 状态码 | 场景 | `detail` |
| --- | --- | --- |
| `401` | 未登录或登录状态失效 | `登录状态无效或已过期，请重新登录` |
| `400` | 上传配置不可用 | `当前项目不支持该上传配置` |
| `400` | 上传配置和凭证类型不匹配 | `project_upload_config_id 与 record_type 不匹配` |
| `400` | 备注、运动日期或图片不符合普通上传规则 | 与普通凭证上传接口一致 |
| `409` | 凭证不在当前用户开放的补传资格中、资格已被消费或项目已隐藏 | `当前凭证没有可用的补传资格` |
| `409` | 赛季、项目或运动日期与资格绑定的原凭证不一致 | `补传信息与原凭证不一致` |
| `409` | 原项目锁定记录已经失效 | `用户未锁定该项目` |
| `409` | 当前处于客户写入保护期 | `赛季开始配置保护期内，暂不允许此操作` |

> **并发规则**
>
> 服务会在提交事务中锁定资格与原凭证。同一资格发生并发提交时，只有首个成功事务能够关闭资格，后续请求返回 `409`。
