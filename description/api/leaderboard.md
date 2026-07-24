# 排行榜接口

## 接口概览

| 方法 | 路径 | 是否鉴权 | 说明 |
| --- | --- | ---: | --- |
| GET | `/flame/api/leaderboard/info` | 是 | 获取当前赛季排行榜基础信息 |

---

## GET /flame/api/leaderboard/info

请求示例：

```http
GET /flame/api/leaderboard/info
Authorization: auth_code
```

成功响应：

```json
[
  {
    "name": "测试用户B",
    "department_name": "研发一组",
    "project_rule_level_id": 1,
    "checkin_count": 15,
    "is_current_user": false
  },
  {
    "name": "测试用户A",
    "department_name": "研发一组",
    "project_rule_level_id": 1,
    "checkin_count": 10,
    "is_current_user": true
  }
]
```

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | string | 用户名称 |
| department_name | string | 用户所属部门名称 |
| project_rule_level_id | number | 用户当前赛季选择的挑战等级 ID |
| checkin_count | number | 当前赛季累计初审通过的有效打卡次数；减重月初不计数，月末同项目最多计一次 |
| is_current_user | boolean | 是否为当前登录用户所在记录 |

数据来源：

```text
leaderboard_snapshot.season_user_id = season_user.id
season_user.user_id = user.id
user.department_id = department.id
season_user.season_id = 当前激活赛季 ID
```

该接口直接读取 `leaderboard_snapshot` 快照表，不实时统计 `proof_record`，也不在后端排序。前端可以基于 `checkin_count` 自行决定展示顺序。

`leaderboard_snapshot` 由后端定时任务刷新，刷新间隔由 `LEADERBOARD_REFRESH_INTERVAL_SECONDS` 控制。默认启动时刷新一次，之后每 900 秒刷新一次；定时文本初审任务写入结果后也会立即刷新。每次刷新会统计当前赛季用户在本次刷新时刻前已初审通过的有效凭证；凭证已通过 `season_user_id` 归属到当前赛季，因此赛季开始前抢先体验的通过凭证同样计入。待初审和初审失败凭证不计入，赛后终审不回溯改变排行榜统计。减重挑战的月初记录不计入，月末记录按同一用户同一项目最多一次统计。
