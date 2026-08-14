# 赛季参与和项目锁定流程

## 核心对象

| 表 | 作用 |
| --- | --- |
| `season` | 赛季配置和当前激活状态 |
| `season_user` | 用户在赛季中的参与记录 |
| `season_user_project` | 用户锁定的赛季项目 |
| `project_level` | 挑战等级和奖励积分 |

赛季状态按以下生命周期流转：

| `season.status` | 含义 | 客户端行为 |
| --- | --- | --- |
| `0` | 未开始 | 不可参与、上传，不展示赛季凭证 |
| `1` | 进行中 | 作为当前赛季，允许参与、上传和查看排行榜 |
| `2` | 结算中 | 停止参与和上传，未定稿凭证不进入客户端历史 |
| `3` | 已结束 | 赛季凭证进入客户端历史 |

正常流转为 `0 -> 1 -> 2 -> 3`。结算中和已结束均不属于当前激活赛季。

---

## 当前赛季

当前激活赛季由以下条件确定：

```text
season.status = 1
ORDER BY season.start_date DESC
LIMIT 1
```

当前赛季不使用进程内缓存。赛季查询、参与检查、项目锁定、项目进度、凭证和排行榜等赛季相关入口均直接查询数据库，确保后台修改 `season.status` 后立即生效。

当没有 `status = 1` 的赛季时，当前赛季查询会返回 `404`。排行榜启动刷新和定时刷新则会跳过本次执行并记录普通信息日志；没有激活赛季（包括只有结算中赛季）是冷启动和赛季切换空窗期的正常状态，不会导致应用启动失败。

---

## 项目锁定

用户锁定项目时：

1. 校验请求赛季必须是当前激活赛季。
2. 校验项目存在且 `project.status = 1`。
3. 查询或创建 `season_user`。
4. 查询 `season_user_project` 是否已有记录。
5. 如果已有效锁定，直接返回成功。
6. 如果锁定数量超过 `season.required_project_count`，返回冲突。
7. 写入或重新激活 `season_user_project`；新锁定项目的 `completion_progress` 初始化为 `0.0000`。
8. 将 `season_user.status` 更新为有效锁定项目数量。

查询已锁定项目和完成进度时同样要求请求中的 `season_id` 是数据库当前激活赛季；没有激活赛季或传入旧赛季 ID 时，不返回该赛季的客户端数据。

---

## 等级锁定

用户锁定挑战等级前，必须满足：

```text
season_user.status == 当前赛季 required_project_count
season_user.level_id IS NULL
project_level.status = 1
```

等级锁定成功后：

```text
season_user.level_id = project_rule_level_id
season_user.participated_at = 当前时间
```

`participated_at` 仅在首次成功锁定等级时写入，代表用户正式报名时间；只锁定项目时保持为空。

---

## 正式参与判断

当前系统将以下条件视为用户正式参与赛季：

```text
season_user 存在
season_user.level_id IS NOT NULL
```

这意味着用户只锁定项目但没有锁定挑战等级时，还不算正式参与。

---

## 报名时间与抢先参与

`SEASON_PARTICIPATION_ALLOWED_DAYS` 控制赛季开始后的报名窗口。开始日前已被后台激活的赛季允许用户抢先参与，不受该天数限制；从开始日当天起计算，开始后第 `N` 天（含）仍可参与，第 `N + 1` 天起未正式参与的用户会被拒绝。默认 `N = 7`。

---

## 项目完成进度

`season_user_project.completion_progress` 表示用户锁定项目在本赛季的完成比例，范围为 `0`～`1`。该字段不参与项目锁定数量和正式参与判断。

后续定时初审任务会筛查超过最小等待时间仍待审的凭证。初审通过时，后端在同一事务中累加对应项目进度并封顶到 `1`；初审失败不改变进度。赛后终审只用于最终结算，不回溯改变赛季内进度。
