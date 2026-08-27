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

### DeepSeek 定时文本初审与手动评测

`tests/test_llm_sport_evaluation.py` 是手动运行的提示词评测脚本，用于验证“项目规则 + 用户 note”生成初审结论、进度增量和审核理由的效果。它通过 `openai.AsyncOpenAI` 调用 DeepSeek 的 OpenAI 兼容接口。

在本地 `.env` 中配置：

```text
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

定时初审服务默认关闭。启用后，每轮任务先从数据库查询当前激活赛季，再筛查其中仍为 `pending` 的有效凭证；没有激活赛季时跳过本轮，模型失败的记录保留待审并在下一次任务中自动补审：

```text
LLM_PRELIMINARY_REVIEW_ENABLED=true
LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS=900
LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS=300
PROGRESS_COMPLETION_SNAP_THRESHOLD=0.0001
```

`LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS` 必须大于 `0`，默认每 15 分钟扫描一次；`LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS` 默认 `300`，仅审核上传满 5 分钟的待审凭证，为用户重传留出窗口。启用前应确认 `DEEPSEEK_API_KEY` 有效；生产任务会以 DeepSeek V4 非思考模式请求 JSON Output，并为偶发的空内容或截断 JSON 自动重试最多 3 次。任务会向 DeepSeek 发送用户填写的 `note`，月末记录还会发送同项目的月初审核摘要。月初记录所需的身高、体重或其他基线数据必须由用户写入备注；任务不会从用户资料补充这些数据，也不会发送凭证图片、用户 ID、赛季 ID、挑战等级 ID 或其他等级规则。

`PROGRESS_COMPLETION_SNAP_THRESHOLD` 控制进度累计后与 `1` 的最大自动补足差额，默认 `0.0001`，可设为 `0` 关闭。该值不得大于数据库四位小数精度的最小单位 `0.0001`，避免提前判定项目完成。

随后仅运行该评测文件（用命令临时启用，避免把开关长期留在 `.env` 中）：

```bash
RUN_LLM_EVALUATION_TESTS=true \
python -m unittest discover -s tests -p 'test_llm_sport_evaluation.py' -v
```

普通 `unittest discover` 默认跳过该测试，不会发起模型请求或消耗 token。生产提示词位于 `app/core/deepseek_preliminary_review.py`，样例位于测试文件顶部；设置本次命令的 `LLM_EVALUATION_STRICT=true` 时，模型的审核状态与样例 `expectedStatus` 不一致会使测试失败。

脚本使用 DeepSeek 的 JSON Output：标准 `https://api.deepseek.com` 地址配合 `response_format={"type": "json_object"}`。提示词中明确要求模型内部先逐项判断、先生成不超过 100 个汉字的 `reviewComment`，再输出最终 `reviewStatus` 和 `progressDelta`；月初意见需要在该范围内完整保留月末审核所需的基线。规则使用派生指标时，提示词要求当前备注提供该指标或完整原始数据，并通过缺失数据反例禁止复用其他示例中的数值。模型不会将详细推理过程返回给前端。

评测与生产服务使用同一套输入结构：项目名称、凭证类型、当前用户已选等级唯一对应的规则文本、规则备注和用户 `note`；月末记录还会发送月初审核摘要。不会发送用户资料、凭证图片、用户 ID、赛季 ID、等级 ID、当前完成进度或其他等级规则。仓库中的阶段型挑战样例均为虚构数据；手动调试时请勿将真实个人健康信息发送到第三方模型。控制台会打印每个样例的原始结构化输出，以及 DeepSeek 返回的 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，供人工比较提示词效果和缓存命中情况。

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
7. 按配置启动定时文本初审任务。
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

图片接口的浏览器私有缓存时长可通过以下配置调整，单位为秒，默认缓存 7 天：

```text
IMAGE_CACHE_MAX_AGE_SECONDS=604800
```
