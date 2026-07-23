# Flame Sport Pheno

企业运动赛季平台的后端服务，基于 FastAPI 和异步 MySQL 实现。项目当前覆盖用户登录、赛季参与、运动项目选择、凭证上传、排行榜快照、用户积分和商品兑换等核心流程。

项目仍处于开发阶段，现有实现主要服务于本地开发和前后端联调。

## 技术栈

- FastAPI
- SQLModel / SQLAlchemy `AsyncSession`
- MySQL 8.4 / asyncmy
- Pydantic Settings
- HTTPX
- Uvicorn

## 当前实现

- **鉴权**：对接钉钉企业内部 H5 微应用免登；后端使用 `auth_code` 换取钉钉 `userId`，并维护进程内认证缓存。
- **用户资料**：查询资料完整度，维护用户身高信息。
- **赛季参与**：查询当前赛季，检查用户参与状态和报名时间。
- **运动项目**：查询项目与挑战规则，锁定赛季项目及挑战等级，并查询已锁定项目的完成进度。
- **运动凭证**：读取项目上传配置，上传 JPG 凭证，查询当前赛季和历史凭证；可由每日 DeepSeek 文本初审写入审核意见、初审状态和项目进度。
- **排行榜**：定时统计当前赛季初审通过的有效凭证数量并生成排行榜快照；减重挑战月初不计数，月末同项目最多计一次。
- **积分商城**：查询商品和积分流水，使用积分兑换商品。
- **本地资源**：管理头像、项目图标、商品图片和运动凭证图片。

当前鉴权缓存和钉钉应用 access token 只存在于单个服务进程中，暂不支持多实例共享登录态、刷新令牌和角色权限。

## 项目结构

```text
app/
  core/          配置、数据库、鉴权、缓存、存储和后台任务
  models/        SQLModel 数据表模型
  repositories/  数据访问与数据库查询
  services/      业务规则、流程编排和事务处理
  routers/       FastAPI 路由和依赖注入
assets/          本地运行期图片资源
description/
  db/            数据库表设计
  business/      业务流程和状态规则
  api/           接口契约
  dev/           本地开发与维护说明
main.py          应用入口与生命周期管理
```

代码按照以下调用方向组织：

```text
router -> service -> repository -> model
```

应用启动时会创建本地资源目录，并启动认证缓存清理、排行榜快照刷新，以及可选的每日 DeepSeek 文本初审任务。

## 本地运行

1. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

2. 根据 `.env.example` 创建 `.env`，配置可用的 MySQL 连接和钉钉企业内部应用凭证。

3. 启动服务：

   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

服务启动后可访问：

- API 根路径：`http://127.0.0.1:8000/flame/api/`
- OpenAPI 文档：`http://127.0.0.1:8000/flame/api/docs`

MySQL Docker 环境的构建和启动方式见 [`description/dev/mysql_docker.md`](description/dev/mysql_docker.md)。

## 项目文档

项目概况和详细文档导航见 [`description/project.md`](description/project.md)。开发接口前建议依次阅读：

1. 相关数据库表设计。
2. 对应业务流程和状态规则。
3. API 请求与响应契约。
4. `router -> service -> repository -> model` 代码实现。

新增或修改接口时，应同步更新对应的 API 和业务文档。除非明确需要调整表结构，不应在接口开发中顺带修改数据库设计文档。
