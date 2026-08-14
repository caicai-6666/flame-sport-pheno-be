# MySQL Docker 说明

MySQL 的 Dockerfile 已迁移至上级目录的 `mysql/Dockerfile`，首次初始化 SQL 位于 `mysql/init/001_flame_sport_pheno.sql`。日常部署优先使用上级目录的 [`docker-compose.yml`](../../../../docker-compose.yml)，完整流程参见 [`docker_compose.md`](docker_compose.md)。

## 单独构建镜像

在上级目录执行：

```bash
docker build -t flame-sport-pheno-mysql:8.4 ./mysql
```

---

## 单独创建数据卷

```bash
docker volume create flame-sport-pheno-mysql-data
```

---

## 单独启动容器

首次使用空卷时，镜像会自动执行 `mysql/init/` 中的 SQL；已有卷不会重复执行。

```bash
docker run -d \
  --name flame-sport-pheno-mysql \
  --restart unless-stopped \
  -p 3307:3306 \
  -v flame-sport-pheno-mysql-data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD=<高强度Root密码> \
  -e MYSQL_DATABASE=flame_sport_pheno \
  -e MYSQL_USER=flame \
  -e MYSQL_PASSWORD=<高强度应用密码> \
  flame-sport-pheno-mysql:8.4
```

---

## 本地连接参数

```text
host: 127.0.0.1
port: 3307
database: flame_sport_pheno
user: flame
password: 启动时设置的 MYSQL_PASSWORD
root password: 启动时设置的 MYSQL_ROOT_PASSWORD
```

Compose 部署时，后端会使用 Docker 网络中的 `mysql:3306`；宿主机或外部测试工具可使用顶层 `.env` 中的 `MYSQL_PORT`（默认 `3307`）。

---

## 既有数据库字段迁移

`SQLModel.metadata.create_all()` 不会为已有表补充字段。对已存在数据库，需要按已部署版本执行相应迁移。

### 赛季结算中状态

启用 `status = 2` 结算中状态前，执行仓库中的
[`20260813_add_season_settling_status.sql`](../../scripts/migrations/20260813_add_season_settling_status.sql)：

```bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < flame-sport-pheno-be/scripts/migrations/20260813_add_season_settling_status.sql
```

该脚本会将旧版 `status = 2` 的已结束赛季迁移为 `status = 3`，并更新字段注释。必须在任何赛季使用新版 `status = 2` 之前执行；执行前必须暂停赛季状态变更并备份数据库，且不可重复执行。

### 积分流水礼品发放状态

部署礼品发放状态能力前，在仓库根目录执行：

```bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < flame-sport-pheno-be/script/migrate-point-record-gift-distribution-status.sql
```

该脚本新增 `point_record.gift_distribution_status`、待发放查询索引和检查约束。历史记录统一初始化为 `pending`；生产执行后必须人工核对并更新已经实际发放的历史兑换流水，避免重复发放。脚本只适用于旧结构，执行前必须完成数据库备份，且不可重复执行。

### 用户建议状态与处理阶段

部署新版用户建议结构前，在仓库根目录执行：

```bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < flame-sport-pheno-be/script/migrate-user-suggestion-status-and-processing-stage.sql
```

该脚本将 `user_suggestion.is_visible` 重命名为 `status`，新增默认值为 `pending` 的 `processing_stage`，并同步索引与检查约束。脚本只适用于旧结构，执行前必须完成数据库备份，且不可重复执行。

### 凭证实际运动日期

部署补传凭证功能前，执行仓库中的
[`20260806_add_proof_record_proof_date.sql`](../../scripts/migrations/20260806_add_proof_record_proof_date.sql)：

```bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < flame-sport-pheno-be/scripts/migrations/20260806_add_proof_record_proof_date.sql
```

该脚本会新增 `proof_record.proof_date`，使用历史 `created_at` 的日期部分回填，并把旧逻辑可能遗留的同用户、同项目、同日期多条有效记录收敛为最新一条。脚本会根据保留的有效通过记录重新同步 `season_user_project.completion_progress`。迁移依赖 `increase` 字段，需先执行下方的“凭证原始进度与实际贡献”迁移。

### 凭证原始进度与实际贡献

部署凭证每日终审进度回退与回补能力前，执行仓库中的
[`20260805_add_proof_record_progress_fields.sql`](../../scripts/migrations/20260805_add_proof_record_progress_fields.sql)：

```bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < flame-sport-pheno-be/scripts/migrations/20260805_add_proof_record_progress_fields.sql
```

迁移会将 `preliminary_progress_delta` 重命名为 `increase`，新增 `progress_delta`，并使用历史 `increase` 保守回填历史原始增量。由于旧系统没有保存被进度条上限截断前的模型返回值，历史超额部分无法精确恢复；新代码上线后的凭证会完整保存两个值。

### 凭证重传实际进度增量

如果目标数据库尚未包含 `proof_record.preliminary_progress_delta`，必须先执行以下迁移，再执行 `20260805_add_proof_record_progress_fields.sql`：

```sql
ALTER TABLE proof_record
  ADD COLUMN preliminary_progress_delta DECIMAL(5,4) NOT NULL DEFAULT 0.0000
    COMMENT '当前版本初审通过实际增加的项目进度' AFTER review_comment;
```

历史凭证的实际贡献无法仅凭旧数据可靠反推，因此该字段使用 `0.0000` 初始化。若历史凭证仍可能被重传，应在启用功能前重新核算当前赛季项目进度。

### 正式报名时间

为记录正式报名时间，需要对已存在数据库执行一次：

```sql
ALTER TABLE season_user
  ADD COLUMN participated_at DATETIME NULL DEFAULT NULL
    COMMENT '正式报名时间（首次锁定挑战等级时写入）' AFTER level_id,
  ADD KEY idx_season_user_participated_at (participated_at);
```

迁移前已经锁定等级的历史记录保留 `participated_at = NULL`，因为无法可靠还原实际报名时间；新记录会在 `POST /flame/api/project/lock_level` 首次成功时写入。
