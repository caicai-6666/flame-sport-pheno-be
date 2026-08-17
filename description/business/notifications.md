# 钉钉工作通知投递

> **文档目的**
>
> 本文说明客户端后端如何把 `notification` 表中的通用业务结果转换为钉钉 Markdown 工作通知，并同步异步任务状态和重试失败通知。

## 1. 功能目标

初审失败、终审失败和奖品发放等业务只负责在自身事务中创建 `pending` 通知。客户端后端在生产模式运行统一定时任务，负责：

1. 把 `message_title` 和有序 `message_fields` 转换为 Markdown。
2. 使用 `user_id` 作为钉钉企业成员 `userId` 提交工作通知。
3. 保存钉钉返回的异步 `task_id`。
4. 查询最终投递结果，将已读和未读统一记为 `delivered`。
5. 重新发送明确失败或中断后超时的通知。

业务写入不直接调用钉钉，因此业务事务不受外部网络延迟影响，通知发送失败也不会回滚已经完成的审核或奖品发放结果。

---

## 2. Markdown 消息

发送端不按通知标题判断业务类型。所有通知统一转换为：

```markdown
### {message_title}

**{key}：** {value}

**{key}：** {value}
```

例如奖品拒绝发放通知为：

```markdown
### 奖品发放结果

**发放结果：** 未发放

**奖品名称：** 运动水杯

**兑换时间：** 2026-08-17 14:30:00

**退还积分：** 500

**处理说明：** 兑换积分已退还
```

`message_title` 同时写入钉钉 `markdown.title`。消息字段按 JSON 数组原始顺序展示；字段值合并为空格分隔的单行文本，并转义 Markdown 和 HTML 边界字符。完整 `msg` 超过 2048 个 UTF-8 字节时保留前序字段并截断尾部，以 `…` 结尾。

---

## 3. 状态流转

通知投递采用以下状态流转：

```text
pending / failed / 超时 processing
  -> processing
  -> accepted
  -> delivered

processing / accepted
  -> failed
  -> 下个检查周期重新发送
```

状态规则如下：

| 状态 | 处理规则 |
| --- | --- |
| `pending` | 优先领取并发送 |
| `processing` | 当前实例已领取；超过保护时间后允许其他轮次回收 |
| `accepted` | 钉钉已返回 `task_id`，定时查询发送进度和结果 |
| `delivered` | 钉钉结果包含目标用户，无论已读或未读均为终态，不再查询 |
| `read` | 兼容历史数据的终态，当前任务不再写入或查询 |
| `failed` | 至少等待一个检查周期后重新领取和发送 |

钉钉进度尚未完成或结果查询暂时异常时保留 `accepted`，避免把实际已经送达的通知重复发送。`accepted` 超过钉钉 24 小时结果查询窗口后转为 `failed`，进入重新发送流程。

---

## 4. 定时处理

通知任务只在 `APP_MODE=production` 且钉钉应用凭证与 `DINGTALK_AGENT_ID` 完整时启动。启动后立即执行一轮，之后按以下配置循环：

```text
DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS=60
```

每轮先查询 `accepted`，再按以下优先级领取最多 20 条发送任务：

1. 新建的 `pending`。
2. 已超过一个检查周期的 `failed`。
3. 超过保护时间的 `processing`。

领取使用 `SELECT ... FOR UPDATE SKIP LOCKED`，状态先提交为 `processing`，再释放数据库事务并调用钉钉。该边界避免外部网络请求长期持有行锁，也允许未来多个实例安全分担发送任务。

---

## 5. 失败与重试

- 发送接口返回业务错误、网络错误或通知内容不符合契约时写入 `failed`。
- 钉钉结果明确包含无效、禁止或失败用户时写入 `failed`。
- 查询进度或结果暂时失败时保持 `accepted`，下一轮继续查询。
- 进程在领取后中断时，`processing` 会在保护时间结束后重新领取。
- 新通知优先于失败重试，永久失败记录不会阻塞新通知。

> **注意**
>
> 钉钉发送接口不提供本项目可用的幂等键。网络在钉钉受理后、本地保存 `task_id` 前中断时，超时重试可能产生重复通知；当前实现提供的是至少一次投递语义。

当前表没有重试次数和失败原因字段。按照业务要求，`failed` 会持续重试；安全日志只记录通知 ID、异常类型、HTTP 状态和钉钉错误码，不记录 access token、消息正文或用户 ID。

---

## 6. 配置与代码入口

相关配置：

```text
DINGTALK_CLIENT_ID
DINGTALK_CLIENT_SECRET
DINGTALK_AGENT_ID
DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS
```

代码入口：

- `app/core/dingtalk.py`
- `app/core/notification_scheduler.py`
- `app/services/notification_delivery_service.py`
- `app/repositories/notification_repository.py`
- `app/models/notification.py`

数据结构参见[用户通知表](../db/notification.md)，初审通知创建规则参见[审核与积分说明](review_and_points.md)。

---

## 7. 验证方式

在后端项目目录运行：

```bash
python -m unittest discover -s tests -v
```

测试使用钉钉客户端和数据库会话替身，不发送真实通知。覆盖 Markdown 转换和转义、UTF-8 字节限制、发送受理、已读与未读送达、查询失败延后、查询窗口过期、明确失败重试和钉钉响应解析。

---

## 8. 已知限制

- 当前通知任务每轮最多发送 20 条、检查 20 条已受理任务，批次数量尚未开放为环境变量。
- `failed` 没有最大重试次数，永久配置错误会按检查周期持续重试。
- 通知表只保存当前 `task_id`，重新发送时不会保留历史钉钉任务 ID。
