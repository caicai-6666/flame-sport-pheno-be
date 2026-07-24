# MySQL Docker 说明

MySQL 的 Dockerfile 已迁移至上级目录的 `mysql/Dockerfile`，首次初始化 SQL 位于 `mysql/init/001_flame_sport_pheno.sql`。日常部署优先使用上级目录的 [`docker-compose.yml`](../../../docker-compose.yml)，完整流程参见 [`docker_compose.md`](docker_compose.md)。

## 单独构建镜像

在上级目录执行：

```bash
docker build -t flame-sport-pheno-mysql:8.4 ./mysql
```

## 单独创建数据卷

```bash
docker volume create flame-sport-pheno-mysql-data
```

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

## 既有数据库字段迁移

`SQLModel.metadata.create_all()` 不会为已有表补充字段。对已存在数据库，需要按已部署版本执行相应迁移。

### 凭证重传实际进度增量

部署“重传先撤销旧版本进度”后，执行仓库中的
[`20260724_add_proof_record_preliminary_progress_delta.sql`](../../scripts/migrations/20260724_add_proof_record_preliminary_progress_delta.sql)：

```bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < flame-sport-pheno-be/scripts/migrations/20260724_add_proof_record_preliminary_progress_delta.sql
```

该字段只能自动记录迁移后新初审通过凭证的实际进度增量。迁移前已经通过的记录无法仅凭现有数据可靠反推其实际增量；若它们仍可能被重传，应在启用功能前重新核算当前赛季项目进度。

### 正式报名时间

为记录正式报名时间，需要对已存在数据库执行一次：

```sql
ALTER TABLE season_user
  ADD COLUMN participated_at DATETIME NULL DEFAULT NULL
    COMMENT '正式报名时间（首次锁定挑战等级时写入）' AFTER level_id,
  ADD KEY idx_season_user_participated_at (participated_at);
```

迁移前已经锁定等级的历史记录保留 `participated_at = NULL`，因为无法可靠还原实际报名时间；新记录会在 `POST /flame/api/project/lock_level` 首次成功时写入。
