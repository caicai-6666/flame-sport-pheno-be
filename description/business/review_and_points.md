# 审核、排行榜和积分业务说明

## 审核状态

`proof_record.review_status` 使用单一字段记录两个阶段的审核结果：赛季内定时初审，以及管理员在赛季期间持续进行的终审。

```text
pending
preliminary_approved
preliminary_rejected
approved
rejected
```

含义：

| 状态 | 说明 |
| --- | --- |
| `pending` | 待初审；用户上传或同运动日期重传后的初始状态 |
| `preliminary_approved` | 初审通过；可计入当前赛季排行榜 |
| `preliminary_rejected` | 初审失败；不计入排行榜，用户可重新上传 |
| `approved` | 终审通过；保留其项目进度和排行榜资格 |
| `rejected` | 终审失败；撤销其项目进度，不计入后续排行榜快照 |

上传接口只创建或重置为 `pending`。定时文本初审任务会根据用户 `note` 与其已选挑战等级对应的一条 `project_rule`，更新为 `preliminary_approved` 或 `preliminary_rejected`；凭证图片保留给管理员人工终审，不发送给模型。

状态流转：

```text
pending -> preliminary_approved -> approved / rejected
pending -> preliminary_rejected -> 用户同运动日期重新上传 -> pending
preliminary_approved -> 用户同运动日期重新上传 -> pending
```

### 定时文本初审任务

任务每轮开始时从数据库查询 `status = 1` 的当前激活赛季，只读取该赛季的有效待审凭证，不扫描结算中或已结束赛季。没有激活赛季时跳过本轮任务：

```text
proof_record.season_user_id -> season_user.id
season_user.season_id = 当前数据库激活赛季 ID
proof_record.status = 1
proof_record.review_status = pending
proof_record.created_at <= 本轮扫描时间 - LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS
```

`season_user.level_id` 与 `proof_record.project_id` 共同定位唯一的启用 `project_rule`。等级 ID、赛季 ID、用户 ID、图片路径和项目其他等级规则都不会发送给模型。模型仅接收项目名称、凭证类型、该条规则、规则备注和用户 `note`；减重挑战的月初记录额外发送用户身高，月末记录额外发送同赛季最早通过月初记录的审核意见。

模型返回 `reviewComment`、`reviewStatus` 和 `progressDelta`。初审通过时，规范化后的 `progressDelta` 保存到 `proof_record.progress_delta`，经过进度条上限分配后实际生效的部分保存到 `proof_record.increase`。普通项目在同一事务内累加 `season_user_project.completion_progress` 并封顶到 `1`；若正向增量累计后距离 `1` 只差一个最小精度单位 `0.0001`，系统会将该条规范化增量补足，避免如三次 `0.3333` 累计为 `0.9999`。减重挑战月初通过时进度保持 `0`，月末通过时直接设为 `1`。

初审失败时，客户端后端在同一事务中创建标题为“运动凭证初审结果”的 `pending` 通知。通知依次保存审核结果、运动项目、凭证日期和审核意见；初审通过不创建通知。通知写入失败时初审结论一并回滚，凭证保持 `pending` 等待后续任务重试。

通知提交钉钉、送达状态同步和失败重试统一遵循[钉钉工作通知投递](notifications.md)，初审服务不直接调用钉钉。

模型异常、超时或返回非法 JSON 时保持 `pending`，下次任务会补审。用户在模型调用期间重传凭证时，旧结果不会覆盖新内容，也不会创建过期通知。

同运动日期重传的审核口径是“先撤销旧版本，再按新版本重算”：上传时若该项目该日期已有有效记录，系统会锁定 `season_user_project` 行、扣回旧记录的 `increase`，并将释放的进度优先回补给同项目下更早上传且 `progress_delta > increase` 的有效通过凭证。旧记录原地重置为待审，同时清零 `progress_delta` 和 `increase`；无论旧记录此前是初审通过还是终审通过，都不会遗留旧进度。新版本初审通过后再从剩余进度空间中分配新的贡献。

管理员终审拒绝凭证时，在同一事务中将该记录的 `increase` 归零，并把释放的进度按 `created_at ASC, id ASC` 回补给同一 `season_user_id + project_id` 下 `status = 1`、审核状态为 `preliminary_approved` 或 `approved` 且 `progress_delta > increase` 的其他凭证。回补完成后同步更新 `season_user_project.completion_progress`。终审操作必须使用状态条件保证幂等，避免重复拒绝造成多次回退。

`累计次数`、`累计天数`、`达标天数`、`累计距离`和`累计时长`是项目总目标，而非单条凭证的拒绝条件。初审只验证该条 `note` 是否满足规则中的单次门槛；通过后由 `progressDelta` 表示其对累计目标的贡献。审核意见不得以“次数不足”“天数不足”或“累计距离不足”等尚未完成累计目标的原因拒绝单条有效记录。

一条凭证默认代表一次有效参与或一个自然日的有效记录。若规则只有允许的运动类型和累计参与/次数目标，例如公司羽毛球或篮球活动，用户在 `note` 中清楚说明实际参加该活动即可通过，不要求额外填写“1次”、时长或参与人数；只有规则明确配置单次时长、距离、配速、海拔等门槛时，才要求对应指标。

初审系统提示词内置步数、跑步、健身、公司运动、登山和减重挑战的固定 few-shot，用于解释“累计目标 + 单次门槛”的通用语义。它们不替代运行时从 `project_rule` 查询到的规则；每次请求仍只传入当前用户、当前项目和已选等级对应的唯一 `ruleContent`。

任务按 `LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS` 固定间隔执行，默认每 15 分钟筛查一次；仅审核已上传至少 `LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS`（默认 5 分钟）的待审凭证，为用户重传留出窗口。本批次有结果写入后立即刷新排行榜快照。

### 管理端单条立即初审

管理端可以使用 `proof_record.id` 立即触发单条文本初审。该入口复用定时任务的规则定位、模型请求、审核结果条件写回、项目进度分配和初审失败通知逻辑，不要求调用方传入审核结论。

立即初审要求凭证所属赛季不是未开始状态，凭证有效且状态为 `pending`，用户已经选择挑战等级，并存在对应的启用项目规则和上传配置。它不受当前激活赛季和最小上传等待时间限制，可用于处理结算中或已结束赛季遗留的待初审凭证；已经进入初审通过、初审失败或终审状态的记录不会重复审核。定时任务的扫描范围保持不变，仍然只处理当前激活赛季。

模型调用期间不会持有数据库事务。写回时仍校验凭证的待审状态、上传时间和用户备注，因此用户重传或其他任务先完成审核后，较早发起的模型结果会被丢弃。初审结果属于激活赛季时，接口会在结果提交后尝试刷新当前排行榜；刷新失败不回滚已经完成的初审。

接口契约参见[管理端接口](../api/admin.md)。

---

## 排行榜

`leaderboard_snapshot` 用于保存排行榜快照。

当前设计口径是统计当前赛季仍具有初审或终审通过状态的有效凭证次数。待初审、初审失败和终审失败凭证不会进入排行榜；管理员终审失败后应刷新排行榜快照。减重挑战的月初记录只建立 BMI 基线，永不计数；同一用户同一项目的任意数量月末通过记录最多计为一次，避免重传或重复记录重复进入排行榜。

快照表只保存 `season_user_id` 和 `checkin_count` 等必要数据，不保存 `rank_no` 和 `calculated_at`：

- 排名由前端基于 `checkin_count` 自行排序计算。
- 最近一次排行榜计算时间由后端进程内运行时状态维护。

当前排行榜读取接口：

```text
GET /flame/api/leaderboard/info
```

该接口直接查询 `leaderboard_snapshot`，关联 `season_user`、`user` 和 `department` 后返回用户名称、部门名称、挑战等级 ID 与 `checkin_count`。接口只返回当前激活赛季的数据，不在请求时实时统计 `proof_record`，也不在后端排序。

接口会根据当前登录 `user_id` 给对应记录增加 `is_current_user = true`，用于前端高亮当前用户所在行。

### 快照刷新任务

应用启动时会根据环境变量启动排行榜快照刷新后台任务。

默认配置：

```text
LEADERBOARD_REFRESH_ENABLED = true
LEADERBOARD_REFRESH_ON_STARTUP = true
LEADERBOARD_REFRESH_INTERVAL_SECONDS = 900
```

刷新策略是全量替换当前赛季快照：

1. 查询当前激活赛季。
2. 删除当前赛季所有旧的 `leaderboard_snapshot` 记录。
3. 统计当前赛季正式参与用户在本次刷新时刻前的有效凭证数量。
4. 将统计结果重新写入 `leaderboard_snapshot`。

统计参与用户条件：

```text
season_user.season_id = 当前激活赛季 ID
season_user.level_id IS NOT NULL
season_user.status >= season.required_project_count
```

统计有效凭证条件：

```text
proof_record.season_user_id = season_user.id
proof_record.status = 1
proof_record.review_status IN (preliminary_approved, approved)
proof_record.created_at < 本次刷新时刻
```

凭证通过 `season_user_id` 已经归属到唯一赛季，因此排行榜不再以 `season.start_date` 作为上传时间下限；赛季开始前的抢先体验凭证初审通过后同样计入当前赛季排行榜。

减重挑战还适用：

```text
record_type = 月初记录：不计数
record_type = 月末记录：同一 season_user + project 最多计 1 次
```

最近一次刷新完成时间保存在进程内 `LeaderboardRuntime.calculated_at`，不写入数据库。

---

## 积分结算

当前积分不是实时发放。赛季离开进行中状态后应先进入 `status = 2` 结算中，用于完成终审、进度校正和积分结算；所有结算工作完成后再切换为 `status = 3` 已结束。

结算结果写入：

```text
season_user.final_points
```

积分流水写入：

```text
point_record
```

赛季内项目完成进度保存在 `season_user_project.completion_progress`。定时初审通过后会在同一事务中更新该字段；终审和积分结算可将项目进度是否达到 `1` 作为辅助判断依据。

---

## 尚未实现的能力

- 人工复核入口。
- 赛季结束统一结算任务。
- 积分商城兑换接口。
