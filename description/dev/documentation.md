# 文档维护说明

## 新接口开发时

新增接口后需要同步更新：

```text
description/api/{router}.md
description/business/{相关业务}.md
```

如果接口涉及新表或表结构调整，再由用户明确要求后更新：

```text
description/db/
```

## 文档职责边界

`api` 文档回答：

```text
接口怎么调用
需要什么参数
返回什么结构
可能有哪些错误
```

`business` 文档回答：

```text
为什么要这样校验
状态如何流转
涉及哪些表
哪些规则跨多个接口共享
```

`dev` 文档回答：

```text
如何本地运行
如何准备资源文件
如何构造 mock 数据
文档如何维护
```

## 命名建议

- 文件名使用小写英文和下划线。
- API 文档按路由命名，例如 `project.md`。
- 业务文档按流程命名，例如 `proof_upload.md`。
- DB 文档按表名命名，例如 `proof_record.md`。
