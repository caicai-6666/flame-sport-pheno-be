# Mock 数据说明

## 当前用途

Mock 数据主要用于本地联调：

- 测试登录用户。
- 测试赛季参与流程。
- 测试项目锁定和等级锁定。
- 测试凭证上传、重复上传和审核状态展示。

## 凭证图片

当前已有示例目录：

```text
assets/images/proof_record/1
```

文件名中包含：

```text
user_id-project_id-timestamp-文件说明.jpg
```

示例：

```text
bb123456-3-20260606090020-健身.jpg
```

对应解析：

| 片段 | 含义 |
| --- | --- |
| `bb123456` | 用户 ID |
| `3` | 项目 ID |
| `20260606090020` | 上传时间 |
| `健身` | 文件说明 |

## project_upload_config_id 约定

当前 mock 约定：

| 项目 | project_upload_config_id |
| --- | ---: |
| 步行 | 1 |
| 健身 | 3 |
| 爬山 | 5 |

## 审核状态

常用 mock 状态：

```text
approved
rejected
pending
```

生成批量 SQL 时，`image_url` 只写完整文件名，不写目录路径。
