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
- 排行榜快照生成任务。
- 赛季结束统一结算任务。
- 积分商城兑换接口。
