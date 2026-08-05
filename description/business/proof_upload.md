# 凭证上传业务说明

## 业务目标

用户正式参与赛季后，可以针对已锁定项目上传运动凭证。凭证用于赛季期间展示、排行榜统计、管理员持续终审和赛季结束后的积分结算。

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

## 上传配置读取

`GET /flame/api/proof/config` 用于返回项目可用的上传凭证类型。上传配置属于低频变更数据，服务层会按 `project_id` 缓存 5 分钟，并在响应中返回短期浏览器私有缓存头。

该缓存只用于读取上传窗口配置，`POST /flame/api/proof/upload` 在写入凭证前仍会查询当前启用的 `project_upload_config`，避免关键写库逻辑依赖过期缓存。

## 前置条件

上传凭证前必须满足：

```text
season_user 存在
season_user.level_id IS NOT NULL
season_user_project.status = 1
project_upload_config.status = 1
```

其中 `project_upload_config_id` 是当前凭证类型的关键外键，后端会校验它必须属于当前 `project_id`。

## 文件保存

凭证图片保存到：

```text
assets/images/proof_record/{season_id}
```

文件名规则：

```text
{user_id}-{project_id}-{timestamp}-{上传文件主名}.jpg
```

数据库 `proof_record.image_url` 当前只保存完整文件名。

读取到激活赛季时，服务会预先创建该赛季 ID 对应的凭证目录；上传时也会再次确保目录存在，避免目录被手动清理后造成写入失败。

## 写库规则

新凭证写入：

```text
proof_record.season_user_id
proof_record.project_id
proof_record.project_upload_config_id
proof_record.image_url
proof_record.note
proof_record.review_status = pending（待初审）
proof_record.review_comment = NULL
proof_record.status = 1
proof_record.created_at
```

`note` 为必填项。用户应填写本次运动的可审核指标，例如距离、时长、次数、配速或累计爬升；后续文本初审任务以该字段和项目等级规则作为判断输入，不向模型发送凭证图片。

## 当天重复上传

重复判断维度：

```text
season_user_id + project_id + project_upload_config_id + created_at 所在自然日 + status = 1
```

如果当天已存在同一上传配置的有效记录，则覆盖：

```text
image_url
note
created_at
review_status = pending
review_comment = NULL
```

当天重传视为一条新的待初审内容：即使旧凭证已经初审通过，也会覆盖旧图片和备注，并清除旧审核意见。这样未来的初审任务只会依据最新的图片和 `note` 判断，不会误用旧结论。

重传前如存在当天同项目的初审通过记录，上传事务会先撤销旧版本的 `increase`，并将释放的进度按上传时间顺序回补给同项目下 `progress_delta > increase` 的其他有效通过凭证，再将重传内容的 `progress_delta` 和 `increase` 清零并置为 `pending`。后续定时初审通过时，系统保存新版本的模型原始增量，并从项目剩余空间中分配新的实际贡献。不同上传配置形成的当天同项目旧通过记录也会被软失效，确保新版本成为唯一有效通过记录。

## 事务和文件清理

接口先保存图片，再写数据库。

如果数据库写入失败，后端会删除本次新保存的图片，避免留下孤儿文件。

如果当天重复上传并更新成功，后端会尽量删除旧图片。

## 历史凭证

`GET /flame/api/proof/current` 基于当前登录用户 ID 查询当前激活赛季凭证。
该接口返回用户上传备注 `note` 和审核意见 `reviewComment`。后者用于展示未来初审任务输出的通过依据或失败原因；未审核或未填写时返回空字符串。

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

当前激活赛季 ID 由服务运行时缓存 `CurrentSeasonRuntime` 提供。缓存未初始化时，接口会先读取当前激活赛季并写入缓存。

查询关系：

```text
season_user.user_id = 当前登录用户 ID
season_user.season_id != 当前激活赛季 ID
proof_record.season_user_id = season_user.id
season_user.season_id = season.id
proof_record.project_id = project.id
proof_record.status = 1
```

返回给前端时，凭证文件名会去掉系统生成前缀，只保留用户上传文件主名。
每条历史凭证会同时返回 `reviewStatus`，便于前端展示待初审、初审结论或终审结论。

示例：

```text
bb123456-3-20260606090020-健身.jpg -> 健身.jpg
```

## 并发保护

写入前会对当前 `season_user` 记录加行锁，避免并发上传时同时插入当天重复凭证。
