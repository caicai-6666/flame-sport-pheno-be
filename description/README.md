# 项目文档地图

本文档是 `description/` 目录的统一导航入口，用于帮助开发者按任务或文档类型定位项目资料。业务背景和系统边界以[项目概况](project.md)为准，所有 Markdown 文档的新增与修改均须遵循[项目文档撰写规范](document-style.md)。

## 1. 推荐阅读顺序

首次参与项目开发时，建议按以下顺序阅读：

1. 阅读[项目概况](project.md)，了解业务流程、领域对象、代码分层和当前限制。
2. 根据本次任务，从下方“按业务主题导航”选择相关业务、API、数据库和开发文档。
3. 阅读对应 Router，再沿 `service -> repository -> model` 追踪实现。
4. 修改文档前阅读[项目文档撰写规范](document-style.md)，并按[文档维护说明](dev/documentation.md)同步相关资料。

> **注意**
>
> `db/` 是数据库设计的事实来源。除非任务明确涉及数据库结构设计，或用户明确要求修改数据库文档，否则不得改动该目录。

---

## 2. 按业务主题导航

下表用于从一项业务能力定位到相关文档和代码入口。

| 业务主题 | 业务规则 | API 契约 | 数据库设计 | 代码入口 |
| --- | --- | --- | --- | --- |
| 登录与鉴权 | [鉴权业务说明](business/authentication.md) | [Auth 接口](api/auth.md) | [用户表](db/user.md) | `app/routers/auth.py` |
| 用户资料 | [用户资料业务说明](business/user_profile.md) | [User 接口](api/user.md) | [用户表](db/user.md)、[部门表](db/department.md) | `app/routers/user.py` |
| 赛季与项目选择 | [赛季与项目选择流程](business/season_project_flow.md) | [Season 接口](api/season.md)、[Project 接口](api/project.md) | [赛季表](db/season.md)、[赛季用户表](db/season-user.md)、[赛季用户项目表](db/season-user-project.md) | `app/routers/season.py`、`app/routers/project.py` |
| 凭证上传与查询 | [凭证上传业务说明](business/proof_upload.md) | [Proof 接口](api/proof.md) | [凭证记录表](db/proof-record.md)、[项目上传配置表](db/project-upload-config.md) | `app/routers/proof.py` |
| 结算赛季补传 | [结算赛季凭证补传](business/supplement.md) | [补传接口](api/supplement.md) | [赛季补传资格表](db/season-supplement-eligibility.md)、[凭证记录表](db/proof-record.md) | `app/routers/supplement.py` |
| 审核、通知、排行榜与积分 | [审核与积分说明](business/review_and_points.md)、[钉钉工作通知投递](business/notifications.md) | [Leaderboard 接口](api/leaderboard.md) | [用户通知表](db/notification.md)、[排行榜快照表](db/leaderboard-snapshot.md)、[积分流水表](db/point-record.md) | `app/core/preliminary_review_scheduler.py`、`app/core/notification_scheduler.py`、`app/routers/leaderboard.py` |
| 积分商城 | [商城业务说明](business/shop.md) | [Shop 接口](api/shop.md) | [商品表](db/product.md)、[积分流水表](db/point-record.md) | `app/routers/shop.py` |
| 用户建议 | [用户建议业务说明](business/suggestion.md) | [Suggestion 接口](api/suggestion.md) | [用户建议表](db/user-suggestion.md) | `app/routers/suggestion.py` |
| 图片与本地资源 | — | [Image 接口](api/image.md)、[Admin 接口](api/admin.md) | 参见各业务表的图片字段 | `app/routers/image.py`、`app/routers/admin.py`、`app/core/storage.py` |
| 管理端内部能力 | 后续随审核功能补充 | [Admin 接口](api/admin.md) | 按具体管理功能读取 | `app/routers/admin.py` |
| 服务健康检查 | — | [Health 接口](api/health.md) | — | `app/routers/health.py` |

---

## 3. API 文档

`api/` 描述接口路径、鉴权方式、输入输出、错误响应和缓存规则。

| 文档 | 内容 |
| --- | --- |
| [Admin 接口](api/admin.md) | Docker 内部管理端接口及资源读取能力 |
| [Auth 接口](api/auth.md) | 登录、认证缓存与资料完整度检查 |
| [Health 接口](api/health.md) | 服务健康检查 |
| [Image 接口](api/image.md) | 头像、商品图片、项目图标、凭证图片和活动海报读取 |
| [Leaderboard 接口](api/leaderboard.md) | 当前赛季排行榜查询 |
| [Project 接口](api/project.md) | 项目、规则、锁定和完成进度查询 |
| [Proof 接口](api/proof.md) | 凭证配置、上传、当前记录和历史记录 |
| [Season 接口](api/season.md) | 当前赛季和参与状态查询 |
| [Shop 接口](api/shop.md) | 商品、积分与兑换 |
| [Suggestion 接口](api/suggestion.md) | 用户建议提交 |
| [补传接口](api/supplement.md) | 结算中赛季可补传凭证查询与补交 |
| [User 接口](api/user.md) | 用户资料读取和更新 |

---

## 4. 业务文档

`business/` 解释跨接口规则、前置条件、状态变化和事务行为。

| 文档 | 内容 |
| --- | --- |
| [鉴权业务说明](business/authentication.md) | 生产与开发登录、钉钉同步和认证缓存 |
| [凭证上传业务说明](business/proof_upload.md) | 凭证保存、重传、查询和文件清理 |
| [审核与积分说明](business/review_and_points.md) | 文本初审、终审、排行榜和积分结算 |
| [钉钉工作通知投递](business/notifications.md) | 通用 Markdown、异步投递状态和失败重试 |
| [赛季与项目选择流程](business/season_project_flow.md) | 赛季参与、项目锁定和挑战等级选择 |
| [商城业务说明](business/shop.md) | 积分查询、商品展示和兑换规则 |
| [结算赛季凭证补传](business/supplement.md) | 当前用户补传资格查询、凭证补交和资格消费规则 |
| [用户建议业务说明](business/suggestion.md) | 建议提交规则和事务边界 |
| [用户资料业务说明](business/user_profile.md) | 用户资料完整度和身高维护 |

---

## 5. 数据库文档

`db/` 描述数据表职责、字段、约束、索引和建表语句。

| 文档 | 数据表 |
| --- | --- |
| [部门表](db/department.md) | `department` |
| [用户通知表](db/notification.md) | `notification` |
| [排行榜快照表](db/leaderboard-snapshot.md) | `leaderboard_snapshot` |
| [积分流水表](db/point-record.md) | `point_record` |
| [商品表](db/product.md) | `product` |
| [项目表](db/project.md) | `project` |
| [项目等级表](db/project-level.md) | `project_level` |
| [项目规则表](db/project-rule.md) | `project_rule` |
| [项目上传配置表](db/project-upload-config.md) | `project_upload_config` |
| [凭证记录表](db/proof-record.md) | `proof_record` |
| [赛季表](db/season.md) | `season` |
| [赛季用户表](db/season-user.md) | `season_user` |
| [赛季用户项目表](db/season-user-project.md) | `season_user_project` |
| [赛季补传资格表](db/season-supplement-eligibility.md) | `season_supplement_eligibility` |
| [用户表](db/user.md) | `user` |
| [用户建议表](db/user-suggestion.md) | `user_suggestion` |

---

## 6. 开发与运维文档

`dev/` 描述运行环境、部署方式、资源管理、测试数据和文档维护流程。

| 文档 | 内容 |
| --- | --- |
| [本地运行说明](dev/local_run.md) | 本地配置、启动方式和后台任务 |
| [Docker Compose 部署](dev/docker_compose.md) | 前后端、MySQL 和管理端内部访问边界 |
| [MySQL Docker 说明](dev/mysql_docker.md) | 数据库容器、初始化和迁移脚本 |
| [本地资源目录说明](dev/assets.md) | 图片目录、文件命名和路径安全 |
| [Mock 数据说明](dev/mock_data.md) | 本地联调数据与资源准备 |
| [文档维护说明](dev/documentation.md) | 功能变更对应的文档同步范围 |

---

## 7. 文档维护规则

文档维护以[项目文档撰写规范](document-style.md)为唯一格式与表达规范，并遵守以下职责边界：

- 新增或修改接口时，同步更新对应的 `api/` 文档。
- 新增或修改跨接口业务规则时，同步更新对应的 `business/` 文档。
- 修改运行、配置、资源或部署流程时，同步更新对应的 `dev/` 文档。
- 明确修改数据库设计时，才同步更新对应的 `db/` 文档。
- 新增、删除或重命名文档时，同步更新本文档中的导航链接。

具体同步流程参见[文档维护说明](dev/documentation.md)。
