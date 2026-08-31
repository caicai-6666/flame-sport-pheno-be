# Docker Compose 部署

上级目录的 `docker-compose.yml` 统一编排当前后端仓库、同级前端仓库和独立的 MySQL 构建目录：

```text
燃动现象/                 执行 Compose 命令的位置
├── .env                  仅供 Compose 读取，禁止提交
├── docker-compose.yml
├── flame-sport-pheno-be/ 当前后端仓库
├── flame-sport-pheno-fe/ 前端仓库
└── mysql/                MySQL Dockerfile 与首次初始化 SQL
```

前端对外暴露 `8080`（可通过 `FRONTEND_PORT` 修改），页面入口为：

```text
http://<host>:8080/flame/
```

前端 Nginx 将 `/flame/api/` 同域代理到后端，后端通过 Docker 网络中的 `mysql:3306` 访问数据库。前端、后端与 MySQL 的宿主机端口分别由顶层 `.env` 的 `FRONTEND_PORT`、`BACKEND_PORT`、`MYSQL_PORT` 配置。

云服务器已有外层 Nginx 时，可将 `/flame/` 代理到 `127.0.0.1:${FRONTEND_PORT}`，将 `/flame/api/` 代理到 `127.0.0.1:${BACKEND_PORT}`；也可以仅代理前端端口，由前端容器继续转发 API。

MySQL 的外部连接地址为 `127.0.0.1:3307`（远程机器使用部署主机地址），应用账号和密码分别来自 `.env` 的 `MYSQL_USER`、`MYSQL_PASSWORD`。该端口会绑定到宿主机全部网络接口，正式生产环境应使用防火墙或安全组限制可信来源。

若宿主机已有服务占用 `3307`，可先停止旧服务，或将顶层 `.env` 的 `MYSQL_PORT` 改为其他空闲端口（例如 `3308`）后再启动。

## 管理端内部服务

管理路由注册在现有 `main:app`，开发和部署均只需启动一个后端服务。管理端容器通过 Compose 服务名直接访问：

```text
http://backend:8000/flame/api/admin
```

关键限制：

- 后端宿主机端口必须绑定回环地址，例如 `127.0.0.1:${BACKEND_PORT:-18000}:8000`，避免绕过 Nginx 直接访问。
- 宿主机 Nginx 必须对 `/flame/api/admin` 及其子路径直接返回 `404`，并放在普通 `/flame/api/` 代理规则之前。
- 管理端容器应通过 `http://backend:8000/flame/api/admin` 访问，不经过宿主机公网域名。
- Docker 内网负责网络隔离，不替代管理员身份认证；真实管理数据接口上线前仍需增加预设密钥登录和短期管理会话。

宿主机 Nginx 的拦截规则示例：

```nginx
location = /flame/api/admin {
    return 404;
}

location ^~ /flame/api/admin/ {
    return 404;
}
```

---

## 首次配置与启动

在上级目录执行：

```bash
# 首次部署前编辑 .env，至少替换 MYSQL_ROOT_PASSWORD、MYSQL_PASSWORD、
# DINGTALK_CLIENT_ID、DINGTALK_CLIENT_SECRET、DINGTALK_AGENT_ID、
# VUE_APP_DINGTALK_CORP_ID 和 VUE_APP_DINGTALK_CLIENT_ID。
docker compose up -d --build
```

Compose 需要把以下赛季保护期和工作通知配置显式注入后端容器；后端镜像不会复制项目 `.env`：

```yaml
environment:
  ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS: ${ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS:-24}
  PROGRESS_COMPLETION_SNAP_THRESHOLD: ${PROGRESS_COMPLETION_SNAP_THRESHOLD:-0.0001}
  DINGTALK_AGENT_ID: ${DINGTALK_AGENT_ID:-}
  DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS: ${DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS:-60}
```

缺少 `DINGTALK_AGENT_ID` 时，登录相关钉钉能力不受影响，但工作通知投递任务不会启动。

`ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS` 同时供管理端和客户后端读取。客户后端按 `Asia/Shanghai` 的赛季开始日 `00:00` 起算，并在保护期内拒绝项目锁定、等级锁定、凭证上传、礼品兑换和首次用户初始化；配置为 `0` 时不冻结。修改该配置后需要重建或重启后端容器才能生效。

`PROGRESS_COMPLETION_SNAP_THRESHOLD` 仅供客户后端读取，默认 `0.0001`。当一条有效凭证写入后的项目进度距 `1` 不超过该值时，系统把尾差同时补入该凭证贡献和项目进度；配置为 `0` 可关闭，允许范围为 `0～0.005`。阈值越大，越可能把本应继续累计的进度提前视为完成，应按项目指标的最大量化尾差设置。修改后同样需要重建或重启 `backend` 容器。

---

## 切换登录模式

顶层 `.env` 的 `APP_MODE` 会仅注入后端容器：

```text
APP_MODE=production   # 默认，钉钉企业内部 H5 免登
APP_MODE=development  # auth_code 直接匹配数据库 user.id
```

切换后重建后端即可：

```bash
docker compose up -d --build backend
```

开发模式不调用钉钉；前端仍调用原有登录接口，但应传入数据库中已有启用用户的 `user.id` 作为 `auth_code`。该设置只影响后端登录解析方式，不会修改前端构建配置。

查看状态和日志：

```bash
docker compose ps
docker compose logs -f frontend backend mysql
```

停止服务但保留数据库卷：

```bash
docker compose down
```

---

## 数据和资源持久化

- MySQL 使用具名卷 `mysql_data`，后端资源使用具名卷 `backend_assets`；执行 `docker compose down` 不会删除这两个卷。
- `mysql/init/001_flame_sport_pheno.sql` 会在空卷首次启动时由 MySQL 自动执行；已有卷不会再次执行该脚本。删除卷（`docker compose down -v`）后再次启动才会重新初始化。
- 后端镜像以 `/workspace` 作为项目根目录，Python 包位于 `/workspace/app`；`backend_assets` 挂载到与其平级的 `/workspace/assets`，保存商品图片、项目图标、头像和用户凭证。该卷与 Git 工作区隔离，频繁 `git pull`、切换分支或重新 clone 后端仓库不会影响已上传资源；请通过 Docker 卷备份流程备份它。
- 后端启动时调用 `SQLModel.metadata.create_all()`，可为全新的 MySQL 卷创建缺失表；它不会迁移已有表结构，已有库仍需按 [`mysql_docker.md`](mysql_docker.md) 的迁移说明执行 SQL。

---

## 备份与恢复示例

在上级目录导出：

```bash
docker compose exec -T mysql sh -c \
  'exec mysqldump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  > flame_sport_pheno.sql
```

导入到已经启动的 Compose 环境：

```bash
docker compose exec -T mysql sh -c \
  'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < flame_sport_pheno.sql
```

上述命令从 MySQL 容器的环境变量读取应用数据库账号；备份文件应妥善保管，不要提交到 Git。
