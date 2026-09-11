# 本地运行说明

## 技术栈

```text
FastAPI
SQLModel
SQLAlchemy AsyncSession
MySQL asyncmy
Pydantic Settings
```

---

## 依赖安装

```bash
pip install -r requirements.txt
```

依赖清单包含 `langgraph`，`app/agent/preliminary_review/workflow.py` 提供独立的异步初审工作流。业务 Service 通过工作流入口执行三节点，节点3直接使用 `openai.AsyncOpenAI.responses.create` 调用模型。包结构和职责参见[初审智能体代码组织](../business/review_and_points.md#初审智能体代码组织)。

本机使用已有 Conda 项目环境时，先激活再安装：

```bash
conda activate flame-sport-pheno-be
python -m pip install -r requirements.txt
```

文件上传接口依赖：

```text
python-multipart
```

---

## 配置

配置类位于：

```text
app/core/config.py
```

复制后端配置模板并按本地环境修改：

```bash
cp .env.example .env
```

仓库内的 `.env.example` 只列出后端 `Settings` 会读取的变量。前端的
`VUE_APP_*`、`FRONTEND_PORT`，以及顶层 Docker Compose 使用的
`MYSQL_*` 等部署变量，应在各自项目或顶层部署目录中维护，不要写入后端 `.env`。

默认数据库连接：

```text
mysql+asyncmy://flame:flame123456@127.0.0.1:3307/flame_sport_pheno?charset=utf8mb4
```

可通过 `.env` 覆盖。

---

## 登录模式

默认使用生产模式：

```text
APP_MODE=production
```

生产模式调用钉钉企业内部 H5 免登。需要本地联调而不访问钉钉时，改为：

```text
APP_MODE=development
```

开发模式下，`POST /flame/api/auth/login` 的 `auth_code` 直接作为本地 `user.id` 查询；用户存在且启用时，服务端写入 `auth_code -> user.id` 缓存并原样返回 `auth_code`。因此前端应传入一个已经存在的用户 ID。开发模式不发起钉钉用户查询，也不启动钉钉 token 预热任务。

钉钉企业内部 H5 微应用登录还需要在 `.env` 中配置：

```text
DINGTALK_CLIENT_ID=ding_xxx
DINGTALK_CLIENT_SECRET=xxx
```

可选的 token 刷新配置：

```text
# 钉钉 HTTP 调用超时，单位：秒。
DINGTALK_HTTP_TIMEOUT_SECONDS=5
# 应用 token 定时预热检查间隔，单位：秒。
DINGTALK_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS=300
# token 剩余该时间时会在下次请求中提前刷新，单位：秒。
DINGTALK_ACCESS_TOKEN_REFRESH_SKEW_SECONDS=300
```

应用获取 token 成功时会在 Uvicorn 控制台输出有效期；失败时会输出安全的 HTTP 状态码和钉钉错误码（例如 `invalidClientIdOrSecret`），不会输出 ClientSecret 或真实 access token。

### 钉钉 Markdown 工作通知

生产模式发送工作通知还需要配置企业内部微应用的正整数 `AgentId`：

```text
DINGTALK_AGENT_ID=123456789
DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS=60
```

`DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS` 必须大于 `0`，同时控制待发送任务扫描、已受理任务结果查询和失败任务的最小重试间隔。`AgentId`、`ClientId` 和 `ClientSecret` 均配置完整时，生产模式会启动通知任务，并在启动后立即处理一次积压通知。

开发模式不会启动钉钉 token 刷新或通知任务，本地 `.env` 可以不配置 `DINGTALK_AGENT_ID`。如需联调真实通知，应使用独立测试应用和测试成员，不得复制生产凭证到开发环境。

### DeepSeek 定时多模态初审与回归测试

初审工作流使用 OpenAI 异步 SDK 调用 DeepSeek 标准 Responses API，发送项目规则、所属赛季日期、记录图片和用户备注，接收严格五字段结果。

在本地 `.env` 中配置：

```text
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

默认值、配置模板与本地配置统一使用已通过本项目真实图文实验的 `deepseek-flash`。运行实验时可直接读取 `.env`，无需额外传入模型名；模型名称按接口标识填写，不拼接版本号。

定时初审服务默认关闭。启用后，每轮任务先从数据库查询当前激活赛季，再筛查其中仍为 `pending` 的有效凭证；没有激活赛季时跳过本轮，模型失败的记录保留待审，并在后续满足数量或等待次数条件的任务中重试：

```text
LLM_PRELIMINARY_REVIEW_ENABLED=true
LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS=900
LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS=300
LLM_PRELIMINARY_REVIEW_MIN_BATCH_SIZE=10
LLM_PRELIMINARY_REVIEW_CONCURRENCY=3
PROGRESS_COMPLETION_SNAP_THRESHOLD=0.0001
```

`LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS` 必须大于 `0`，默认每 15 分钟扫描一次；`LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS` 默认 `300`，仅审核上传满 5 分钟的待审凭证，为用户重传留出窗口。任务按 `Asia/Shanghai` 判断赛季边界，并在结束日次日 `00:00` 前 5 分钟停止扫描；最后 5 分钟遗留的记录由管理端结算流程调用立即初审。启用前应确认密钥及所配模型支持图片和结构化输出。节点以非思考模式请求 `text.format.json_schema`，设置 `strict = true`，单次最多输出 2048 tokens；不进行格式重试，SDK 自动重试也已关闭。月末同时发送月初评价；用户 ID、赛季 ID、等级 ID、平台用户资料和本地图片路径不发送给模型。

`LLM_PRELIMINARY_REVIEW_MIN_BATCH_SIZE` 和 `LLM_PRELIMINARY_REVIEW_CONCURRENCY` 必须为正整数；无效配置会禁用定时初审并记录错误。数量阈值默认 `10`，不足阈值但有待审记录时，第三次连续扫描会直接审核；空扫描、切换赛季或重启会重置等待计数。间隔仍从上一轮结束后计算，不保证固定墙钟时刻触发。并发默认 `3`，按用户项目分组，同组先月初后其他记录、顺序处理；每条使用独立会话，避免跨任务共享事务。计数与并发限制均为进程内机制，多实例仍可能重复调用模型。

Service 将完整图片、分段定位、运动日期和凭证所属赛季起止日期交给工作流；首节点在线程池中按定位生成无损 WebP 内存切片，没有定位则保留整图。节点2使用 `prepared_images` 生成 `messages`：system 追加项目规则、赛季起止日期（含首尾当日）和可选月初评价，user 按顺序包含编号图片与最后的用户备注。节点3将消息适配为 Responses 输入后直接提交，按 `evidence`、`reasoning`、`result_type`、`delta`、`comment` 校验并映射业务结果。图片文件缺失、损坏或定位非法会阻止本条初审并保留待审状态。填写的运动日期超出所属赛季时，Service 直接初审不通过；所属赛季不存在或起止日期无效时保留待审。图片实际日期的赛季归属判断由随请求发送的提示词约束。

外围回归测试使用临时图片、模拟数据库和模型，不发起外部请求。在后端仓库根目录执行：

```bash
python -m unittest tests.test_preliminary_review_node tests.test_preliminary_review_output tests.test_preliminary_review_context tests.test_preliminary_review_images tests.test_preliminary_review_outer tests.test_preliminary_review_workflow -v
```

`PROGRESS_COMPLETION_SNAP_THRESHOLD` 控制进度累计后与 `1` 的最大自动补足差额，默认 `0.0001`，可设为 `0` 关闭，最大允许 `0.005`。例如累计 12 次时四位小数增量 `0.0833` 会形成 `0.0004` 尾差，阈值至少需要覆盖该差额。阈值越大，越可能提前判定完成，设置时应以现有项目指标的最大量化尾差为依据。

`experiment/preliminary_review_test3/run.py` 提供三张 test3 图片拼接、分段后执行完整子图的真实实验，包含时长推断场景；命令、mock 条件和输出说明参见 [test3 实验说明](../../experiment/preliminary_review_test3/README.md)。此实验会真实请求模型，结果存入实验目录下的 `output/`。

[test4 实验](../../experiment/preliminary_review_test4/README.md) 验证真实健身照片与噪音混合时的时长推断，包含数据库青铜规则的30分钟门槛与模拟45分钟门槛对照。实验真实调用模型，结果和分析保存于独立 `output/` 目录。

[图片相关性测试矩阵](../../experiment/preliminary_review_relevance/README.md) 使用现有图片和模拟规则，覆盖无关图、噪音、时长门槛及健身图用于跑步或爬山的7个场景。真实调用结果与提示词快照保存在实验目录中；环境代理故障时该实验直连配置地址，不影响业务客户端配置。

[comment 正反例实验](../../experiment/preliminary_review_comment/README.md) 使用相同健身图片分别验证30分钟与45分钟门槛，检查五字段顺序、简短评论及业务意见映射；这是会产生模型费用的真实测试。

[单张打卡与意外备注实验](../../experiment/preliminary_review_missing_checkin/README.md) 观察仅开始图、仅结束图以及是否说明忘记打卡时的模型判断；该真实实验不预设豁免政策，结果与分析保存在独立 `output/` 目录。

[旧漏打卡规则实验](../../experiment/preliminary_review_missing_checkin_policy/README.md) 记录历史版本中明示遗漏与具体时间两个前提的验证，包含开始/结束遗漏正例及缺信息、时长不足等反例，保留提示词调整前后的真实结果。

[图片与备注共同判断实验](../../experiment/preliminary_review_combined_evidence/README.md) 验证当前信息互补、冲突以图片为准的规则，包含单图加开始时间、单图加总时长、信息不足和图片冲突4组。旧漏打卡特殊前提已取消，历史报告不代表当前规则。

[test5 无指标照片实验](../../experiment/preliminary_review_test5/README.md) 验证健身场景照片不包含时长记录时，备注分别提供达标时长、不足时长或缺失时长的 3 组真实审核结果；日期与规则均为模拟，结果保存在独立 `output/`。

[图片日期要求实验](../../experiment/preliminary_review_image_date/README.md) 验证无日期图片拒绝、图片日期与提交当日一致通过及日期不一致拒绝。图片日期现在是硬性要求，备注不能补足；此前 test5 与图文联合报告保留历史行为。

回归测试不调用外部模型，不消费 token。真实联调应通过 `run_preliminary_review` 传入带赛季范围的完整任务，确认实际模型支持图片及严格 Schema；接口不支持时直接报错，不自动降级。日志记录 `input_tokens`、`cached_tokens` 和 `output_tokens`，不打印完整消息与图片。

---

## 启动

推荐在项目根目录启动：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

也可以通过 IDE 或 Python 直接运行 `app/main.py`。配置模块始终按文件位置读取项目根目录的 `.env`，不依赖进程当前工作目录；从 `app/` 目录启动时也不会错误寻找 `app/.env`。

`app/main.py` 中的直接运行配置用于脚本启动；本地开发更建议使用上面的 Uvicorn 命令，以便明确控制监听地址和热更新参数。

所有服务接口均以 `/flame/api` 为公共前缀。OpenAPI 文档、Redoc 和 OpenAPI JSON 分别为：

```text
/flame/api/docs
/flame/api/redoc
/flame/api/openapi.json
```

---

## 启动初始化

应用启动时会：

1. 为当前数据库创建缺失的数据表（不会修改已有表结构）。
2. 创建本地资源目录。
3. 启动认证缓存过期清理任务。
4. 在 `APP_MODE=production` 时启动应用 access token 定时预热任务。
5. 在钉钉应用凭证和 `AgentId` 完整时启动工作通知投递任务。
6. 启动排行榜快照刷新任务。
7. 按配置启动定时多模态初审任务。
8. 注册所有路由。

数据库尚未配置 `status = 1` 的赛季时，应用仍可正常冷启动。排行榜刷新任务会跳过本次刷新并记录信息日志，待后续激活赛季后在下一次调度周期自动开始刷新。

赛季开始配置保护期通过以下环境变量控制，单位为小时：

```text
ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS=24
```

客户后端固定按 `Asia/Shanghai` 的 `season.start_date 00:00` 计算保护期，不依赖本地机器或容器时区。配置为 `0` 时不冻结客户业务写入；建议提交始终允许。

本地资源目录包括：

```text
assets/images/avatar
assets/images/project_icon
assets/images/product
assets/images/proof_record
```

排行榜刷新相关环境变量：

```text
LEADERBOARD_REFRESH_ENABLED=true
LEADERBOARD_REFRESH_ON_STARTUP=true
LEADERBOARD_REFRESH_INTERVAL_SECONDS=900
```

默认每 15 分钟刷新一次；本地调试时可以将 `LEADERBOARD_REFRESH_INTERVAL_SECONDS` 改小，例如 `60`。

头像、商品图片和项目图标的浏览器私有缓存时长可通过以下配置调整，单位为秒，默认缓存 7 天：

```text
IMAGE_CACHE_MAX_AGE_SECONDS=604800
```

运动凭证图片不受该配置影响。由于重传会沿用原凭证 URL，客户侧与管理侧凭证图片固定禁止浏览器缓存。
