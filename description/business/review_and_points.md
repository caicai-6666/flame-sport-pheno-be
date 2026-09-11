# 审核、排行榜和积分业务说明

## 初审智能体代码组织

模型初审能力集中在 `app/agent/preliminary_review/`，各模块职责如下：

| 模块 | 职责 |
| --- | --- |
| `schemas.py` | 模型请求、原图、准备后的记录图片和结果类型 |
| `state.py` | 工作流单次运行的请求、`prepared_images`、`messages` 与结果状态 |
| `image_processing.py` | 解码整图、复用定位校验并在内存中裁剪图片 |
| `prompt/preliminary_review_prompt.py` | 图片与备注共同判断、冲突时图片优先的提示词及 22 组审核示例，导出 `SYSTEM_PROMPT` |
| `output_contract.py` | 新版五字段 JSON Schema、本地严格校验及业务结果转换 |
| `prompt/context_renderer.py` | 渲染附带项目上下文的 system 消息和包含图片、备注的 user 消息 |
| `node.py` | 图片准备、上下文渲染及模型判断三个节点；直接调用 OpenAI 异步 Responses API，校验严格五字段结果 |
| `workflow.py` | 构建 `START → prepare_images → render_context → review → END` 工作流，提供 `run_preliminary_review` 异步入口 |

`prepare_images` 已实现图片准备：在线程池中完整解码图片，复用上传定位校验，再按 `image_segments.segments` 顺序裁剪。坐标基于实际保存的整图，不再次旋转或缩放；切片去除定位区域之外的边距，使用无损 WebP 编码以保留截图文字和透明通道。所有处理使用内存缓冲区，不创建临时文件，也不修改原图或原始请求。

节点将 `tuple[PreparedReviewImage, ...]` 写入 `state.prepared_images`，供后续节点读取。每张图片包含以下字段：

| 字段 | 含义 |
| --- | --- |
| `index` | 从 `1` 开始的图片序号，与输入定位顺序一致 |
| `x`、`y` | 该图片区域在原始整图中的左上角像素坐标 |
| `width`、`height` | 图片区域的像素宽高 |
| `media_type` | 切片为 `image/webp`；整图兼容分支保留实际原格式 |
| `content` | 可独立解码的图片文件字节，不包含在对象的默认日志表示中 |

没有定位的历史图片保留为一张完整图片，复用原始字节和实际媒体类型，不猜测切分位置，也不重复压缩。独立文本评测允许 `request.image = None`，此时输出空元组；业务 Service 仍要求提供有效图片。损坏图片、媒体类型不符或非法定位会抛出初审技术异常，中断后续节点，由外围保留待审状态，不生成初审拒绝结论。

`render_context` 读取原始请求和 `prepared_images`，在线程池中生成两条 OpenAI Chat Completions 格式消息，并写入 `state.messages`。它要求图片准备节点已运行，不自行读图或再次裁剪，也不修改原始请求。

消息按以下顺序组织：

1. `system` 首部完整保留现有 `SYSTEM_PROMPT`，随后以 `【项目上下文开始】` 引出项目名称、凭证类型、规则指标、赛季起止日期和可选规则补充说明。月初评价存在时，放在规则之后，以 `【月初评价开始】` 引出；无值时省略该段。
2. `user` 首先包含可选运动日期，再按 `prepared_images` 顺序交错加入编号文本和图片内容。每张图片前仅使用 `【第k张图片开始】` 标识序号，之后为独立 `image_url` 内容项。图片字节编码为带实际媒体类型的 Base64 Data URL，不作为普通文字发送。
3. 所有图片之后追加 `【用户备注开始】` 和原始备注。无图片的独立文本评测保留日期和备注，不生成虚构图片内容。

各段只使用开始标识，不生成结束标识。用户备注和运动日期只出现在 user 消息，渲染器不改写所引用的系统提示词正文。节点不写日志或文件保存完整消息，图片及 Base64 仅在本次工作流内存中保存。图片内容项格式参见 [OpenAI 图片输入文档](https://developers.openai.com/api/docs/guides/images-vision)。

`review` 直接消费节点2的 `messages`，保持 system 前缀和图文顺序，将 `text` / `image_url` 内容适配为 Responses API 的 `input_text` / `input_image`。图片使用 `detail = high`。节点直接调用 `AsyncOpenAI.responses.create`，不再保留 `DeepSeekPreliminaryReviewClient` 类或客户端单例。

定时、立即和补交初审均由 Service 准备单条上下文后调用 `run_preliminary_review` 工作流入口。工作流只返回模型结果，不持有数据库会话、不保存检查点、不写入凭证或通知；异常向调用方传播，由业务层保留现有失败处理。

定时调度仍位于 `app/core/preliminary_review_scheduler.py`；规则读取、补交快照、进度分配、通知创建及事务控制仍位于 `app/services/preliminary_review_service.py` 和既有 Repository。Service 传入单条用户项目任务，三个节点完成内存切片、上下文渲染和图文联合初审。

---

## 新版提示词与严格输出契约

新版提示词采用图片与备注共同判断、冲突时以图片为准的原则。图片已充分满足项目要求时，不因备注中的数值冲突而拒绝；图片明确不达标时，备注不能推翻图片。图片之间存在无法解释的关键冲突时，不挑选有利证据；重复截图不重复计数，缺失信息不使用示例或用户资料补齐。月初保留基线和目标，月末依据基线与当前图片比较。模型意见只写简短审核理由，不输出完整思维过程或声称已执行写库、通知等操作。

备注可以补充图片未覆盖的本次活动、起止时间、总时长或其他指标；无需说明遗漏原因，也不要求固定措辞。在图片已证明提交运动当日的前提下，单张相关照片加备注提供的总时长或缺失端时间，可共同用于判断达标，除非项目明确要求某项指标必须由图片证明。总时长已明确时不强制补齐所有起止时刻，也不反向编造图片未显示的时间。

图片日期是所有项目及凭证阶段的硬性前提：图片必须清晰证明本次运动或测量发生于提交的 `proof_date`，且位于原赛季内。备注不能补足图片缺失的日期；无日期、日期模糊、只有时分或日期与提交当日不一致时，即使时长达标也不通过。上传日和审核日不代替运动日，补交仍按原运动日判断。相册展示的拍摄日期须明确关联本次现场照片，截图日期、状态栏时钟、文件名及无关图日期不能替代活动日期。多图可联合取证，但不能将日期套用于无法关联的活动。

图片与备注有实际冲突时采用图片；图片缺少信息不算冲突。结合两者后仍缺少必要信息才要求补充。证据注明来源，关键指标由备注提供时短评注明“结合备注”，不将用户陈述写成图片已证实的事实。此前漏打卡需要同时说明遗漏及具体时间的前提已取消。

图片取证先判断与项目允许运动类型的相关性，再核验日期及指标。跑步记录不能由骑行或单纯步数替代；山景、海拔标牌不能独立证明登山或累计爬升；健身可接受规则允许的器械、瑜伽、居家训练或运动记录，不限定健身房。场景相关不等于已经证明参与或指标达标，月初、月末测量凭证按所需指标判断，不强制运动场景。

多图中的无关生活照或其他活动图片不参与本次计算，有效证据独立达标时不因噪音而整体拒绝。但声称属于本次活动、存在关键冲突的图片不能随意当作噪音忽略，备注也不能把明确的其他运动类型改为当前项目。

图片取证先由项目规则确定核验范围，重点读取相关数值、单位、指标名称及日期，例如时长、距离、配速、步数、海拔、累计爬升和体重。不得混淆运动时长与总耗时、海拔与爬升、体重与变化量、单次与累计统计。日期需区分实际运动或测量日期、截图时间和统计周期，并与本次运动日期及月初/月末阶段核对；缺失或冲突时如实记录，日期按图片日期硬性要求判断，其他指标按项目要求判断，不猜测日期或额外要求所有项目提供全部指标。

赛季范围以凭证关联的 `season_user.season_id` 查询到的起止日期为准，两个边界均包含当日，并追加到 system 项目上下文。定时、历史立即初审和结算补交共用该来源，补交不会改用当前激活赛季。Service 在调用工作流前检查凭证填写的 `proof_date`，超出范围时直接初审不通过且增量为 `0`；赛季不存在或起止日期倒置属于技术异常，保留待审状态。独立调用工作流兼容未提供范围；若提供则起止日期必须成对且顺序有效。

新版提示词要求核对本次活动的实际运动或测量日期：赛季外活动即使数值达标也不通过，备注、上传日期及截图日期不能覆盖图片中的活动日期。补交上传时间可以在赛季结束后，实际活动仍须属于原赛季。历史趋势和辅助基线中的其他日期不直接导致整条拒绝；必要日期证据不足时不通过，不猜测赛季或年份。节点3已将图片日期约束随新消息发送给模型；填写日期的范围校验仍由 Service 直接执行。

`PreliminaryReviewOutput` 按以下顺序声明必填字段，禁止额外字段和类型强制转换：

| 字段 | 类型与约束 | 含义 |
| --- | --- | --- |
| `evidence` | `array[string]`，1～5 条，每条 1～60 字符 | 带图片编号或来源的证据 |
| `reasoning` | `string`，1～120 字符 | 规则对应关系、判断结论和必要增量计算的摘要 |
| `result_type` | `通过` 或 `不通过` | 初审结论 |
| `delta` | 有限数值，`0～1` | 本条凭证的原始进度增量 |
| `comment` | `string`，1～60 字符 | 一句话说明结论与关键原因的用户短评 |

本地校验要求“不通过”的 `delta` 为 `0`；月初通过为 `0`、月末通过为 `1` 的规则由提示词说明，既有业务层仍按凭证类型规范化进度。`to_review_result()` 将中文结论映射到既有审核枚举，将增量转为 `Decimal`，普通及月末记录的 `review_comment` 使用模型 `comment`，不展示字段名或增量计算。月初记录在短评后追加完整证据与理由，供月末读取基线；不截断初始指标和目标。字段长度约束确保组合后不超过数据库的 500 字符，避免截断月初关键基线；不新增数据库字段。

22 组 few-shot 覆盖图片与备注互补、实际冲突、项目相关性、日期范围、累计目标、阶段基线、单图补充总时长或起止时间，以及合并后信息仍不足等情况。示例只是审核口径说明，不作为当前请求的图片事实。

节点3使用配置中的标准 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL`，通过 `text.format = {type: json_schema, name: preliminary_review, strict: true, schema: ...}` 请求严格五字段输出。使用 `reasoning.effort = none`、`temperature = 0`、`max_output_tokens = 2048` 和非流式响应；不自动切换 Beta、替换模型或降级到普通 JSON。接口依据为 [DeepSeek Responses API](https://api-docs.deepseek.com/api/create-response/) 与 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。

单次节点调用只发送一次请求，SDK `max_retries = 0`，无格式重试。仅接受 `completed` 的完整 assistant 文本结果，再由 `PreliminaryReviewOutput` 做本地校验与转换。拒答、截断、空内容、旧字段、非法增量、接口错误和超时都作为技术异常传播，保留待审；任务取消正常向上传递。后续扫描仍可依照外围阈值重新审核，不代表跨扫描永久只调用一次。日志仅记录 token 总量与缓存命中，不记录完整消息、图片或模型输出。

旧文本提示词及旧客户端已删除。当前回归测试使用真实 SDK 和模拟 HTTP 验证请求与响应协议，不调用真实 DeepSeek；部署前仍需针对实际配置的模型、账户权限和图片样本验证识别质量及严格输出支持。

---

## 审核状态

`proof_record.review_status` 使用单一字段记录两个阶段的审核结果：赛季内定时初审，以及管理员在赛季期间持续进行的终审。

```text
pending
preliminary_approved
preliminary_rejected
approved
rejected
```

含义：

| 状态 | 说明 |
| --- | --- |
| `pending` | 待初审；用户上传或同运动日期重传后的初始状态 |
| `preliminary_approved` | 初审通过；可计入当前赛季排行榜 |
| `preliminary_rejected` | 初审失败；不计入排行榜，用户可重新上传 |
| `approved` | 终审通过；保留其项目进度和排行榜资格 |
| `rejected` | 终审失败；撤销其项目进度，不计入后续排行榜快照 |

上传接口只创建或重置为 `pending`。定时多模态初审任务会根据凭证图片、用户 `note`、赛季日期与其已选挑战等级对应的一条 `project_rule`，更新为 `preliminary_approved` 或 `preliminary_rejected`；凭证图片按分段定位处理后发送给模型，也保留给管理员人工终审。

状态流转：

```text
pending -> preliminary_approved -> approved / rejected
pending -> preliminary_rejected -> 用户同运动日期重新上传 -> pending
preliminary_approved -> 用户同运动日期重新上传 -> pending
```

### 定时多模态初审任务

任务每轮开始时从数据库查询 `status = 1` 的当前激活赛季，只读取该赛季的有效待审凭证，不扫描结算中或已结束赛季。没有激活赛季时跳过本轮任务；当前时间到达赛季结束日次日 `00:00` 前 5 分钟后也停止扫描，把最后上传但尚未达到最小等待时间的记录留给结算期立即初审：

```text
proof_record.season_user_id -> season_user.id
season_user.season_id = 当前数据库激活赛季 ID
proof_record.status = 1
proof_record.review_status = pending
proof_record.created_at < 本轮扫描时间 - LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS
```

调度保持每轮结束后等待既定间隔，启动时不立即补跑。每次扫描按当前不同待审凭证数量判断，达到 `LLM_PRELIMINARY_REVIEW_MIN_BATCH_SIZE`（默认 `10`）就执行；非空但不足阈值时累计等待次数，第三次仍不足则执行本轮所有符合条件的记录。相同凭证不会因多轮出现而重复累计数量。执行触发、空扫描、赛季切换、无激活赛季、到达停止时间、扫描异常及任务重启都会清零等待计数；模型失败后仍待审的记录下次重新参与阈值判断。计数只保存在当前进程内，重启后重新等待，不具备分布式调度锁。 上传文件仍采用秒级时间戳命名，现有回写校验不能可靠区分同秒、同文件名且备注相同的图片覆盖；独立上传版本号或唯一文件名尚未实现。

任务按 `season_user_id + project_id` 分组，不同组通过 `LLM_PRELIMINARY_REVIEW_CONCURRENCY`（默认 `3`）限制并发数。同组串行，先处理月初，再按上传时间和 ID 处理其他记录，确保月末查询发生在同批月初任务完成之后。每条任务重新检查待审状态、赛季和上传等待时间，并使用独立数据库会话；失败只影响本条。程序关闭时会取消并等待所有并发工作任务退出。

工作流每次接收一条 `PreliminaryReviewRequest`：项目名称、凭证类型、用户所选等级的规则与说明、用户备注、运动日期、所属赛季起止日期（`season_start_date`、`season_end_date`）、可选月初基线，以及 `PreliminaryReviewImage`。图片对象包含完整文件字节、实际媒体类型和可空的 `image_segments`；Service 在线程池中读取并校验图片与定位，且不在等待读图或模型期间持有事务。图片缺失或无效时保留待审状态。Service 传入整图和可空定位，由工作流首节点准备内存图片；历史记录无定位时保留整图。模型节点接收准备后的图片内容。原有三项结果契约保持为初审状态、模型意见、进度增量。

`season_user.level_id` 与 `proof_record.project_id` 共同定位唯一的启用 `project_rule`。等级 ID、赛季 ID、用户 ID、用户资料、图片路径和项目其他等级规则都不会发送给模型。模型接收项目名称、凭证类型、该条规则、规则备注、赛季起止日期、运动日期、记录图片和用户 `note`；月末记录额外接收同赛季同项目最早有效月初记录的 `preliminary_review_comment`。月初图片或备注必须提供规则判断所需的初始数据，例如 BMI 分档规则所需的身高和体重；后端不读取或补充平台保存的身高。月初记录初审通过后即使被终审通过，独立初审意见仍会保留，不受 `review_comment` 终审覆盖影响。

模型返回 `evidence`、`reasoning`、`result_type`、`delta` 和 `comment`，节点映射为既有模型意见、初审状态和进度增量。初审意见只写入 `proof_record.preliminary_review_comment`；`review_comment` 为管理员终审专用字段，初审不得写入。客户端记录查询同时返回 `preliminaryReviewComment` 和 `finalReviewComment`，分别展示两个阶段意见；既有 `reviewComment` 保持兼容，按当前审核阶段选择其中一个字段。规范化后的 `progressDelta` 保存到 `proof_record.progress_delta`，经过进度条上限分配后实际生效的部分保存到 `proof_record.increase`。普通项目在同一事务内累加 `season_user_project.completion_progress` 并封顶到 `1`；若正向增量累计后距离 `1` 不超过 `PROGRESS_COMPLETION_SNAP_THRESHOLD`，系统会把尾差补入本条凭证的 `progress_delta` 和 `increase`，确保凭证贡献合计与项目进度一致。默认阈值为 `0.0001`，允许按部署环境提高到 `0.005`，可覆盖 `12 × 0.0833 = 0.9996` 等多次量化尾差。所有使用月初、月末凭证类型的阶段型项目共用同一规则：月初通过时只建立基线，进度保持 `0`；月末通过时直接设为 `1`。

初审失败时，客户端后端在同一事务中创建标题为“运动凭证初审结果”的 `pending` 通知。通知依次保存审核结果、运动项目、凭证日期和审核意见；初审通过不创建通知。通知写入失败时初审结论一并回滚，凭证保持 `pending` 等待后续任务重试。

通知提交钉钉、送达状态同步和失败重试统一遵循[钉钉工作通知投递](notifications.md)，初审服务不直接调用钉钉。

模型异常、超时或返回非法 JSON 时保持 `pending`，下次任务会补审。用户在模型调用期间重传凭证时，旧结果不会覆盖新内容，也不会创建过期通知。

同运动日期重传的审核口径是“先撤销旧版本，再按新版本重算”：上传时若该项目该日期已有有效记录，系统会锁定 `season_user_project` 行、扣回旧记录的 `increase`，并将释放的进度优先回补给同项目下更早上传且 `progress_delta > increase` 的有效通过凭证。旧记录原地重置为待审，同时清零 `progress_delta` 和 `increase`；无论旧记录此前是初审通过还是终审通过，都不会遗留旧进度。新版本初审通过后再从剩余进度空间中分配新的贡献。

管理员终审拒绝凭证时，在同一事务中将该记录的 `increase` 归零，并把释放的进度按 `created_at ASC, id ASC` 回补给同一 `season_user_id + project_id` 下 `status = 1`、审核状态为 `preliminary_approved` 或 `approved` 且 `progress_delta > increase` 的其他凭证。回补完成后同步更新 `season_user_project.completion_progress`。终审操作必须使用状态条件保证幂等，避免重复拒绝造成多次回退。

`累计次数`、`累计天数`、`达标天数`、`累计距离`和`累计时长`是项目总目标，而非单条凭证的拒绝条件。初审结合本条图片与备注验证单次门槛和赛季归属，冲突时以图片为准；通过后由 `progressDelta` 表示其对累计目标的贡献。审核意见不得以“次数不足”“天数不足”或“累计距离不足”等尚未完成累计目标的原因拒绝单条有效记录。

一条凭证默认代表一次有效参与或一个自然日的有效记录。若规则只有允许的运动类型和累计参与/次数目标，例如公司羽毛球或篮球活动，图片证据能够证明实际参加该活动时可通过，不要求额外填写“1次”、时长或参与人数；只有规则明确配置单次时长、距离、配速、海拔等门槛时，才要求对应指标。

初审系统提示词内置普通累计挑战和月初、月末阶段型挑战的 few-shot，用于解释“累计目标 + 单次门槛”和“建立基线 + 期末比较”的通用语义。它们不替代运行时从 `project_rule` 查询到的规则；每次请求仍只传入当前项目和已选等级对应的唯一 `ruleContent`。月初意见需要保留规则要求的初始值、必要派生值和匹配目标，具体指标不由后端硬编码。规则按派生指标分档时，本条图片或备注必须提供该指标或计算它所需的全部原始数据；提示词同时提供缺少原始数据的拒绝反例，禁止模型复用其他示例中的数值。

任务按 `LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS` 固定间隔执行，默认每 15 分钟筛查一次；仅审核已上传至少 `LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS`（默认 5 分钟）的待审凭证，为用户重传留出窗口。停止边界固定按 `Asia/Shanghai` 计算。本批次有结果写入后立即刷新排行榜快照。

### 管理端单条立即初审

管理端可以使用 `proof_record.id` 立即触发单条多模态初审。该入口复用定时任务的规则定位、模型请求、审核结果条件写回、项目进度分配和初审失败通知逻辑，不要求调用方传入审核结论。

立即初审要求凭证不属于未开始赛季，凭证有效且状态为 `pending`，用户已经选择挑战等级，并存在对应的启用项目规则和上传配置。它不受最小上传等待时间限制，主要用于赛季刚进入结算时处理截止前遗留记录，也保留对已结束赛季历史遗留记录的补审能力；已经进入初审通过、初审失败或终审状态的记录不会重复审核。

已经完成补交且资格状态为 `2` 的记录不得使用通用立即初审入口，必须进入补交专用初审服务。

模型调用期间不会持有数据库事务。写回时仍校验凭证的待审状态、上传时间、用户备注和图片文件名，因此用户重传或其他任务先完成审核后，较早发起的模型结果会被丢弃。初审结果属于激活赛季时，接口会在结果提交后尝试刷新当前排行榜；刷新失败不回滚已经完成的初审。

接口契约参见[管理端接口](../api/admin.md)。

### 补交专用初审

补交专用初审只处理结算中赛季里 `season_supplement_eligibility.status = 2` 且凭证仍为 `pending` 的记录。它从资格行的 `preliminary_review_context_snapshot` 读取项目名称、参赛等级、凭证类型、规则指标和规则备注，不读取当前启用的 `project_rule`，因此后续赛季修改项目指标不会改变旧赛季补交记录的审核口径。

快照缺失、结构非法或等级与 `season_user.level_id` 不一致时，服务直接失败并保留待审状态，禁止回退到实时规则。初审结果与资格状态在同一事务内提交：初审通过时资格更新为 `3` 并等待管理员终审；初审失败时资格恢复为 `1`，允许用户根据初审意见再次补交；模型或持久化异常时保持 `2`，由管理端结算任务下次重试。

三类入口的职责如下：

| 服务 | 赛季范围 | 规则来源 | 触发方式 |
| --- | --- | --- | --- |
| 定时初审 | 仅进行中，且距离结束超过 5 分钟 | 当前启用规则 | 客户端后端定时任务 |
| 立即初审 | 进行中、结算中或已结束的非补交待审记录 | 当前启用规则 | 管理端按凭证调用 |
| 补交初审 | 仅结算中的已补交待审记录 | 补传资格快照 | 管理端结算调用 |

---

## 排行榜

`leaderboard_snapshot` 用于保存排行榜快照。

当前设计口径是统计当前赛季仍具有初审或终审通过状态的有效凭证次数。待初审、初审失败和终审失败凭证不会进入排行榜；管理员终审失败后应刷新排行榜快照。阶段型项目的月初记录只建立审核基线，永不计数；同一用户同一项目的任意数量月末通过记录最多计为一次，避免重传或重复记录重复进入排行榜。

快照表只保存 `season_user_id` 和 `checkin_count` 等必要数据，不保存 `rank_no` 和 `calculated_at`：

- 排名由前端基于 `checkin_count` 自行排序计算。
- 最近一次排行榜计算时间由后端进程内运行时状态维护。

当前排行榜读取接口：

```text
GET /flame/api/leaderboard/info
```

该接口直接查询 `leaderboard_snapshot`，关联 `season_user`、`user` 和 `department` 后返回用户名称、部门名称、挑战等级 ID 与 `checkin_count`。接口只返回当前激活赛季的数据，不在请求时实时统计 `proof_record`，也不在后端排序。

接口会根据当前登录 `user_id` 给对应记录增加 `is_current_user = true`，用于前端高亮当前用户所在行。

### 快照刷新任务

应用启动时会根据环境变量启动排行榜快照刷新后台任务。

默认配置：

```text
LEADERBOARD_REFRESH_ENABLED = true
LEADERBOARD_REFRESH_ON_STARTUP = true
LEADERBOARD_REFRESH_INTERVAL_SECONDS = 900
```

刷新策略是全量替换当前赛季快照：

1. 查询当前激活赛季。
2. 删除当前赛季所有旧的 `leaderboard_snapshot` 记录。
3. 统计当前赛季正式参与用户在本次刷新时刻前的有效凭证数量。
4. 将统计结果重新写入 `leaderboard_snapshot`。

统计参与用户条件：

```text
season_user.season_id = 当前激活赛季 ID
season_user.level_id IS NOT NULL
season_user.status >= season.required_project_count
```

统计有效凭证条件：

```text
proof_record.season_user_id = season_user.id
proof_record.status = 1
proof_record.review_status IN (preliminary_approved, approved)
proof_record.created_at < 本次刷新时刻
```

凭证通过 `season_user_id` 已经归属到唯一赛季，因此排行榜不再以 `season.start_date` 作为上传时间下限；赛季开始前的抢先体验凭证初审通过后同样计入当前赛季排行榜。

所有使用月初、月末凭证类型的阶段型项目还适用：

```text
record_type = 月初记录：不计数
record_type = 月末记录：同一 season_user + project 最多计 1 次
```

最近一次刷新完成时间保存在进程内 `LeaderboardRuntime.calculated_at`，不写入数据库。

---

## 积分结算

当前积分不是实时发放。赛季离开进行中状态后应先进入 `status = 2` 结算中，用于完成终审、进度校正和积分结算；所有结算工作完成后再切换为 `status = 3` 已结束。

结算结果写入：

```text
season_user.final_points
```

积分流水写入：

```text
point_record
```

赛季内项目完成进度保存在 `season_user_project.completion_progress`。定时初审通过后会在同一事务中更新该字段；终审和积分结算可将项目进度是否达到 `1` 作为辅助判断依据。

---

## 尚未实现的能力

- 人工复核入口。
- 赛季结束统一结算任务。
- 积分商城兑换接口。
