# 排行榜快照表：leaderboard_snapshot

## 表作用
`leaderboard_snapshot` 表用于存储当前赛季的排行榜快照数据。
当前平台中，排行榜按照用户在当前赛季的打卡次数进行排名。  
排行榜数据由定时任务每天固定时间统计并写入本表，前端排行榜页面直接读取本表，避免每次访问时实时统计凭证记录。

当前设计中，本表只保存最新排行榜快照，不保留每日历史快照。  
定时任务每次执行时会覆盖更新当前赛季的排行榜数据。

---

## 字段说明

| 字段名         | 类型            | 是否必填 |            默认值 | 说明                                   |
| -------------- | --------------- | -------: | ----------------: | -------------------------------------- |
| id             | BIGINT UNSIGNED |       是 |              自增 | 排行榜快照记录主键 ID                  |
| season_user_id | BIGINT UNSIGNED |       是 |                无 | 赛季用户记录 ID，关联 `season_user.id` |
| rank_no        | INT UNSIGNED    |       是 |                无 | 当前排名                               |
| checkin_count  | INT UNSIGNED    |       是 |                 0 | 当前赛季累计打卡次数                   |
| calculated_at  | DATETIME        |       是 | CURRENT_TIMESTAMP | 本次排行榜计算时间                     |

---

## 字段设计说明

### id

排行榜快照记录的唯一标识。

使用 `BIGINT UNSIGNED AUTO_INCREMENT` 作为主键。

---

### season_user_id

赛季用户记录 ID。

该字段关联 `season_user.id`。
`season_user` 已经唯一表示：

```text
某个用户 + 某个赛季
```

因此本表不再重复存储 `season_id` 和 `user_id`，避免数据冗余。

通过 `season_user_id` 可以间接获取：

```text
season_id
user_id
用户名称
用户头像
用户部门
```

---

### rank_no

当前排名。

排名由定时任务根据用户当前赛季累计打卡次数计算得出。

示例：

```text
1
2
3
18
```

---

### checkin_count

当前赛季累计打卡次数。

该字段是排行榜排序的核心指标。

当前计算口径为：

```text
当前 season_user_id 下，status = 1 的 proof_record 数量
```

由于平台采用月末统一审核模式，赛季期间大量凭证尚未审核，因此排行榜不依赖 `review_status = approved`，而是统计有效上传记录数量。

---

### calculated_at

排行榜计算时间。

用于标识当前排行榜快照是什么时候生成的。

例如：

```text
2026-07-17 03:00:00
```

前端或后台可以根据该字段展示“排行榜更新时间”。

---

## MySQL 建表语句

```sql
CREATE TABLE leaderboard_snapshot (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '排行榜快照记录ID',
  season_user_id BIGINT UNSIGNED NOT NULL COMMENT '赛季用户记录ID',
  rank_no INT UNSIGNED NOT NULL COMMENT '当前排名',
  checkin_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '当前赛季累计打卡次数',
  calculated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '排行榜计算时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_leaderboard_snapshot_season_user (season_user_id),
  KEY idx_leaderboard_snapshot_rank_no (rank_no),
  KEY idx_leaderboard_snapshot_checkin_count (checkin_count),
  KEY idx_leaderboard_snapshot_calculated_at (calculated_at),
  CONSTRAINT fk_leaderboard_snapshot_season_user
    FOREIGN KEY (season_user_id) REFERENCES season_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='排行榜快照表';
```