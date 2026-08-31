# 凭证上传业务说明

## 业务目标

用户正式参与赛季后，可以针对已锁定项目上传运动凭证。凭证用于赛季期间展示、排行榜统计、管理员持续终审和赛季结束后的积分结算。进行中赛季使用普通上传接口；结算中赛季只能通过补传资格绑定的原凭证进行补交，具体规则参见[结算赛季凭证补传](supplement.md)。

当前业务实现位于：

```text
app/services/proof_service.py
```

对应接口：

```text
GET /flame/api/proof/config
GET /flame/api/proof/current
GET /flame/api/proof/history
POST /flame/api/proof/upload
```

---

## 上传配置读取

`GET /flame/api/proof/config` 用于返回项目可用的上传凭证类型。上传配置属于低频变更数据，服务层会按 `project_id` 缓存 5 分钟，并在响应中返回短期浏览器私有缓存头。

该缓存只用于读取上传窗口配置，`POST /flame/api/proof/upload` 在写入凭证前仍会查询当前启用的 `project_upload_config`，避免关键写库逻辑依赖过期缓存。

---

## 前置条件

上传凭证前必须满足：

```text
season.status = 1
season_user 存在
season_user.level_id IS NOT NULL
season_user_project.status = 1
project_upload_config.status = 1
```

其中 `project_upload_config_id` 是当前凭证类型的关键外键，后端会校验它必须属于当前 `project_id`。

如果当前时间处于赛季开始后的配置保护期，上传会在创建赛季目录、读取图片和写入数据库前返回 `409`。保护期口径参见[赛季参与和项目锁定流程](season_project_flow.md#赛季开始配置保护期)。

如果请求中的赛季存在但已经隐藏或未激活，服务会立即拒绝本次上传。激活状态直接来自数据库，不依赖进程内赛季缓存。

---

## 文件保存

凭证图片保存到：

```text
assets/images/proof_record/{season_id}
```

文件名规则：

```text
{user_id}-{project_id}-{timestamp}-{上传文件主名}.webp
```

数据库 `proof_record.image_url` 当前只保存完整文件名。

客户端可以提交 JPEG、PNG 或 WebP。后端不直接保存客户端字节，而是解码图片、修正 EXIF 方向，并按质量 82 统一重编码为 WebP；图片像素尺寸保持不变，带透明通道的源图继续保留透明效果。图片转换在线程池执行，避免 CPU 密集编码阻塞其他异步请求。

读取到激活赛季时，服务会预先创建该赛季 ID 对应的凭证目录；上传时也会再次确保目录存在，避免目录被手动清理后造成写入失败。

---

## 写库规则

新凭证写入：

```text
proof_record.season_user_id
proof_record.project_id
proof_record.project_upload_config_id
proof_record.image_url
proof_record.note
proof_record.proof_date
proof_record.review_status = pending（待初审）
proof_record.review_comment = NULL
proof_record.status = 1
proof_record.created_at
```

`note` 为必填项。用户应填写本次运动的可审核指标，例如距离、时长、次数、配速或累计爬升；后续文本初审任务以该字段和项目等级规则作为判断输入，不向模型发送凭证图片。

`proof_date` 为必填日期，表示本次运动实际发生的日期。前端只应展示赛季起止日期至当天之间的可选日期，普通上传默认选择当天；后端仍会校验该日期满足：

```text
season.start_date <= proof_date <= min(season.end_date, 今天)
```

因此用户不能提前上传未来日期，也不能补传赛季外日期。`created_at` 始终保存实际上传时间，不会被补传日期覆盖。

---

## 同运动日期重复上传

重复判断维度：

```text
season_user_id + project_id + proof_date + status = 1
```

不论凭证类型是否相同，同项目同运动日期最多保留一条有效记录。用户再次提交该日期时覆盖原记录：

```text
image_url
note
project_upload_config_id
proof_date
created_at
review_status = pending
review_comment = NULL
```

同运动日期重传视为一条新的待初审内容：即使旧凭证已经初审通过或终审通过，也会覆盖旧图片和备注，并清除旧审核意见。这样未来的初审任务只会依据最新的图片和 `note` 判断，不会误用旧结论。

重传前系统会先撤销旧记录的 `increase`，并将释放的进度按上传时间顺序回补给同项目下 `progress_delta > increase` 的其他有效通过凭证，再将重传内容的 `progress_delta` 和 `increase` 清零并置为 `pending`。后续定时初审通过时，系统保存新版本的模型原始增量，并从项目剩余空间中分配新的实际贡献。

---

## 事务和文件清理

接口先保存图片，再写数据库。

如果数据库写入失败，后端会删除本次新保存的图片，避免留下孤儿文件。

如果同运动日期重复上传并更新成功，后端会尽量删除旧图片。

---

## 历史凭证

`GET /flame/api/proof/current` 基于当前登录用户 ID 查询当前激活赛季凭证，并返回 `proofDate`，供前端标识已上传日期和“重新上传”入口。
该接口返回用户上传备注 `note`，并同时返回 `preliminaryReviewComment` 和 `finalReviewComment`，分别用于展示初审与终审意见。既有 `reviewComment` 继续按当前审核阶段选择来源：初审状态读取 `preliminary_review_comment`，终审状态读取终审专用的 `review_comment`；待审核或对应意见未填写时返回空字符串。

查询关系：

```text
season_user.user_id = 当前登录用户 ID
season_user.season_id = 当前激活赛季 ID
proof_record.season_user_id = season_user.id
season_user.season_id = season.id
proof_record.project_id = project.id
proof_record.status = 1
```

`GET /flame/api/proof/history` 基于当前登录用户 ID 查询过往赛季历史凭证，并排除当前激活赛季的上传记录。

`current` 每次请求都会从数据库读取当前激活赛季。`history` 不依赖当前赛季，返回 `season.status IN (2, 3)` 的结算中或已结束赛季凭证；`status = 0` 的未开始赛季和 `status = 1` 的当前激活赛季不会出现在客户端历史记录中。

查询关系：

```text
season_user.user_id = 当前登录用户 ID
season.status IN (2, 3)
proof_record.season_user_id = season_user.id
season_user.season_id = season.id
proof_record.project_id = project.id
proof_record.status = 1
```

返回给前端时，凭证文件名会去掉系统生成前缀，只保留用户上传文件主名。
`current` 和 `history` 的每条记录还会返回 `imageUrl`，格式为 `/flame/api/image/proof_record/{proof_record_id}`；前端请求该地址时仍需携带登录态。图片接口会按凭证归属再次校验当前用户，不能仅通过递增 ID 读取其他用户的凭证。

凭证重传沿用相同的 `proof_record_id` 和图片接口 URL，因此凭证图片响应禁止浏览器缓存。客户端每次请求该 URL 都会读取当前凭证文件，避免重传后继续展示旧图片；该规则不影响头像、商品图片和项目图标的私有缓存。

每条历史凭证会同时返回 `proofDate` 和 `reviewStatus`，便于前端展示实际运动日期、待初审、初审结论或终审结论。

示例：

```text
bb123456-3-20260606090020-健身.webp -> 健身.webp
```

---

## 并发保护

写入前会对当前 `season_user` 记录加行锁，避免并发上传时同时写入同项目同运动日期的重复凭证。
