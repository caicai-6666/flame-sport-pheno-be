# 审核、排行榜和积分业务说明

## 审核状态

`proof_record.review_status` 建议取值：

```text
pending
approved
rejected
```

含义：

| 状态 | 说明 |
| --- | --- |
| `pending` | 用户已上传，等待审核 |
| `approved` | 审核通过 |
| `rejected` | 审核拒绝 |

当前上传接口只创建或重置为 `pending`。审核接口尚未实现。

## 排行榜

`leaderboard_snapshot` 用于保存排行榜快照。

当前设计口径是统计当前赛季有效上传次数，而不是实时审核通过次数。这样能支持赛季期间的活跃排行展示。

快照表只保存 `season_user_id` 和 `checkin_count` 等必要数据，不保存 `rank_no` 和 `calculated_at`：

- 排名由前端基于 `checkin_count` 自行排序计算。
- 最近一次排行榜计算时间由后端进程内运行时状态维护。

当前排行榜读取接口：

```text
GET /api/leaderboard/info
```

该接口直接查询 `leaderboard_snapshot`，关联 `season_user`、`user` 和 `department` 后返回用户名称、部门名称、挑战等级 ID 与 `checkin_count`。接口只返回当前激活赛季的数据，不在请求时实时统计 `proof_record`，也不在后端排序。

接口会根据当前登录 `user_id` 给对应记录增加 `is_current_user = true`，用于前端高亮当前用户所在行。

### 快照刷新任务

应用启动时会根据环境变量启动排行榜快照刷新后台任务。

默认配置：

```text
LEADERBOARD_REFRESH_ENABLED = true
LEADERBOARD_REFRESH_ON_STARTUP = true
LEADERBOARD_REFRESH_INTERVAL_SECONDS = 86400
```

刷新策略是全量替换当前赛季快照：

1. 查询当前激活赛季。
2. 删除当前赛季所有旧的 `leaderboard_snapshot` 记录。
3. 统计当前赛季正式参与用户在赛季开始后、本次刷新时刻前的有效凭证数量。
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
proof_record.created_at >= season.start_date 00:00:00
proof_record.created_at < 本次刷新时刻
```

最近一次刷新完成时间保存在进程内 `LeaderboardRuntime.calculated_at`，不写入数据库。

## 积分结算

当前积分不是实时发放，而是在赛季结束后统一审核和结算。

结算结果写入：

```text
season_user.final_points
```

积分流水写入：

```text
point_record
```

## 尚未实现的能力

- 审核人员后台审核接口。
- 赛季结束统一结算任务。
- 积分商城兑换接口。
