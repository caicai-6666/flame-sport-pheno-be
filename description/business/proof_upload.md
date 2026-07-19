# 凭证上传业务说明

## 业务目标

用户正式参与赛季后，可以针对已锁定项目上传运动凭证。凭证用于赛季期间展示、排行榜统计和赛季结束后的审核结算。

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

## 写库规则

新凭证写入：

```text
proof_record.season_user_id
proof_record.project_id
proof_record.project_upload_config_id
proof_record.image_url
proof_record.note
proof_record.review_status = pending
proof_record.review_comment = NULL
proof_record.status = 1
proof_record.created_at
```

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

## 事务和文件清理

接口先保存图片，再写数据库。

如果数据库写入失败，后端会删除本次新保存的图片，避免留下孤儿文件。

如果当天重复上传并更新成功，后端会尽量删除旧图片。

## 并发保护

写入前会对当前 `season_user` 记录加行锁，避免并发上传时同时插入当天重复凭证。
