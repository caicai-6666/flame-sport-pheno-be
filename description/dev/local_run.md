# 本地运行说明

## 技术栈

```text
FastAPI
SQLModel
SQLAlchemy AsyncSession
MySQL asyncmy
Pydantic Settings
```

## 依赖安装

```bash
pip install -r requirements.txt
```

文件上传接口依赖：

```text
python-multipart
```

## 配置

配置类位于：

```text
app/core/config.py
```

默认数据库连接：

```text
mysql+asyncmy://flame:flame123456@127.0.0.1:3307/flame_sport_pheno?charset=utf8mb4
```

可通过 `.env` 覆盖。

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

### DeepSeek 文本初审与手动评测

`tests/test_llm_sport_evaluation.py` 是手动运行的提示词评测脚本，用于验证“项目规则 + 用户 note”生成初审结论、进度增量和审核理由的效果。它通过 `openai.AsyncOpenAI` 调用 DeepSeek 的 OpenAI 兼容接口。

在本地 `.env` 中配置：

```text
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

每日初审服务默认关闭。启用后，它只审核 `CurrentSeasonRuntime.season_id` 对应赛季、执行日零点前仍为 `pending` 的有效凭证；模型失败的记录保留待审，次日自动补审：

```text
LLM_PRELIMINARY_REVIEW_ENABLED=true
LLM_PRELIMINARY_REVIEW_DAILY_TIME=02:00
LLM_PRELIMINARY_REVIEW_TIMEZONE=Asia/Shanghai
```

`LLM_PRELIMINARY_REVIEW_DAILY_TIME` 必须为 `HH:MM`。启用前应确认 `DEEPSEEK_API_KEY` 有效；生产任务会以 DeepSeek V4 非思考模式请求 JSON Output，并为偶发的空内容或截断 JSON 自动重试最多 3 次。任务会向 DeepSeek 发送用户填写的 `note`，减重挑战月初记录还会发送身高，月末记录会发送月初审核摘要。不会发送凭证图片、用户 ID、赛季 ID、挑战等级 ID 或其他等级规则。

随后仅运行该评测文件（用命令临时启用，避免把开关长期留在 `.env` 中）：

```bash
RUN_LLM_EVALUATION_TESTS=true \
python -m unittest discover -s tests -p 'test_llm_sport_evaluation.py' -v
```

普通 `unittest discover` 默认跳过该测试，不会发起模型请求或消耗 token。生产提示词位于 `app/core/deepseek_preliminary_review.py`，样例位于测试文件顶部；设置本次命令的 `LLM_EVALUATION_STRICT=true` 时，模型的审核状态与样例 `expectedStatus` 不一致会使测试失败。

脚本使用 DeepSeek 的 JSON Output：标准 `https://api.deepseek.com` 地址配合 `response_format={"type": "json_object"}`。提示词中明确要求模型内部先逐项判断、先生成不超过 40 个汉字的 `reviewComment`，再输出最终 `reviewStatus` 和 `progressDelta`；不会将详细推理过程返回给前端。

评测与生产服务使用同一套输入结构：项目名称、凭证类型、当前用户已选等级唯一对应的规则文本、规则备注和用户 `note`；减重挑战还会发送身高或月初审核摘要。不会发送凭证图片、用户 ID、赛季 ID、等级 ID、当前完成进度或其他等级规则。仓库中的减重样例均为虚构数据；手动调试时请勿将真实个人身高、体重等健康信息发送到第三方模型。控制台会打印每个样例的原始结构化输出，以及 DeepSeek 返回的 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，供人工比较提示词效果和缓存命中情况。

## 启动

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

`main.py` 中的直接运行配置当前使用固定局域网地址；本地开发更建议使用上面的 uvicorn 命令。

所有服务接口均以 `/flame/api` 为公共前缀。OpenAPI 文档、Redoc 和 OpenAPI JSON 分别为：

```text
/flame/api/docs
/flame/api/redoc
/flame/api/openapi.json
```

## 启动初始化

应用启动时会：

1. 创建本地资源目录。
2. 启动认证缓存过期清理任务。
3. 配置钉钉凭证时，启动应用 access token 定时预热任务。
4. 启动排行榜快照刷新任务。
5. 按配置启动每日文本初审任务。
6. 注册所有路由。

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
LEADERBOARD_REFRESH_INTERVAL_SECONDS=86400
```

本地调试时可以将 `LEADERBOARD_REFRESH_INTERVAL_SECONDS` 改小，例如 `60`。
