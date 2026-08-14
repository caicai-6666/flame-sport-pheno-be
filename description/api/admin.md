# 管理端接口

## 用途与访问边界

`admin` 路由专门服务管理端，后续用于提供用户头像、运动凭证和审核所需的数据。它注册在现有后端应用中：

```text
main:app
```

管理端容器必须绕过宿主机公网 Nginx，通过 Docker Compose 服务名访问：

```text
http://backend:8000/flame/api/admin
```

宿主机将后端端口仅绑定到 `127.0.0.1`，公网 Nginx 对 `/flame/api/admin` 及其子路径直接返回 `404`。网络隔离只限制外部网络直接访问；后续新增真实管理数据接口前，还应实现预设密钥登录和短期管理会话，不能把 Docker 内网本身视为完整身份认证。

---

## 路由前缀

```text
/flame/api/admin
```

---

## 接口列表

当前路由提供以下接口。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/flame/api/admin` | 管理端内部路由存活校验 |
| `GET` | `/flame/api/admin/avator` | 根据头像地址读取用户头像 |
| `GET` | `/flame/api/admin/project_icon` | 根据图标地址读取项目图标 |
| `POST` | `/flame/api/admin/project_icon` | 将上传图片转换为无损 WebP 项目图标 |
| `GET` | `/flame/api/admin/product` | 根据奖品图片地址读取奖品图片 |
| `POST` | `/flame/api/admin/product/replace` | 用新奖品图片地址取代旧地址 |
| `GET` | `/flame/api/admin/proof_record/{proof_record_id}` | 根据凭证记录读取运动凭证图片 |

---

## GET `/flame/api/admin`

成功响应：

```json
{
  "code": 200,
  "service": "admin"
}
```

该接口当前只用于确认管理路由和 Docker 内部网络可用，不读取业务数据。

---

## GET `/flame/api/admin/avator`

根据管理端已有数据中的头像地址读取头像文件。路由名称按当前管理端约定使用 `avator`。

请求示例：

```http
GET /flame/api/admin/avator?avatar_url=%2Fxxx.webp
```

Query 参数：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `avatar_url` | `string` | 是 | 用户头像地址，例如 `/xxx.webp`；应使用 URL 编码传递 |

处理流程：

1. 去除头像地址开头的 `/` 或 `\\`。
2. 拼接到头像目录 `assets/images/avatar`。
3. 校验最终路径没有逃逸出头像目录。
4. 返回头像文件，不查询 `user` 表。

成功响应示例：

```http
Content-Type: image/webp
Cache-Control: private, no-store
```

用户头像统一返回 `image/webp`。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 400 | 头像地址为空或仅包含空白 | `头像地址不能为空` |
| 400 | 头像地址逃逸出头像目录 | `头像路径非法` |
| 404 | 头像文件不存在 | `头像文件不存在` |
| 422 | 缺少 `avatar_url` | FastAPI 参数校验错误 |

---

## GET `/flame/api/admin/project_icon`

根据管理端已有项目数据中的图标地址读取项目图标。

请求示例：

```http
GET /flame/api/admin/project_icon?icon_url=%2Fxxx.webp
```

Query 参数：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `icon_url` | `string` | 是 | 项目图标地址，例如 `/xxx.webp`；应使用 URL 编码传递 |

后端会去除地址开头的 `/` 或 `\\`，兼容历史 `/project_icon/xxx.webp` 路径前缀，然后拼接到 `assets/images/project_icon` 并校验路径安全。

成功响应示例：

```http
Content-Type: image/webp
Cache-Control: private, no-store
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 400 | 图标地址为空或仅包含空白 | `项目图标路径不能为空` |
| 400 | 图标地址逃逸出项目图标目录 | `项目图标路径非法` |
| 404 | 项目图标文件不存在 | `项目图标文件不存在` |
| 422 | 缺少 `icon_url` | FastAPI 参数校验错误 |

---

## POST `/flame/api/admin/project_icon`

该接口供 Docker 内部管理端上传项目图标，并按最终相对地址保存到 `assets/images/project_icon`。接口接受 JPEG、PNG 或 WebP，服务端统一转换为无损 WebP，因此透明边缘和像素信息不会丢失。

请求类型：

```http
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `icon_url` | `string` | 是 | 最终相对地址，例如 `/跑步.webp`，必须以 `.webp` 结尾，最长 255 个字符 |
| `image` | `File` | 是 | JPEG、PNG 或 WebP 图片，最大 5 MiB，最长边不超过 1600 像素 |

Docker 内部请求示例：

```bash
curl -X POST 'http://backend:8000/flame/api/admin/project_icon' \
  -F 'icon_url=/跑步.webp' \
  -F 'image=@./跑步.png;type=image/png'
```

成功时返回 `201 Created`：

```json
{
  "icon_url": "/跑步.webp",
  "size_bytes": 1992
}
```

存储规则：

1. 去除 `icon_url` 开头的 `/` 或 `\`，并兼容历史 `/project_icon/xxx.webp` 路径前缀。
2. 校验最终路径没有逃逸出 `assets/images/project_icon`。
3. 校验地址以 `.webp` 结尾，上传媒体类型和实际内容属于 JPEG、PNG 或 WebP，且最长边不超过 1600 像素。
4. 在线程池中无损编码为 WebP，保留透明通道。
5. 先写入同目录临时文件，再原子替换到目标地址；已存在的同名文件会被覆盖。

> **注意**
>
> 客户端项目图标读取响应默认可缓存 7 天。更换图标时应生成新的唯一 `icon_url`，避免重用已缓存地址后继续显示旧图。

错误响应：

| 状态码 | 场景 | `detail` |
| --- | --- | --- |
| `400` | 存储地址为空或路径非法 | `项目图标路径非法` 等对应提示 |
| `400` | 存储地址不是 `.webp` | `项目图标存储地址必须以 .webp 结尾` |
| `400` | 媒体类型或实际内容不受支持 | `项目图标仅支持 JPEG、PNG 或 WebP` 或 `上传内容不是有效的项目图标` |
| `400` | 图片最长边超过 1600 像素 | `项目图标最长边不能超过 1600 像素` |
| `413` | 图片超过 5 MiB | `项目图标不能超过 5 MiB` |
| `422` | 缺少必填字段或 `icon_url` 超长 | FastAPI 参数校验错误 |

---

## GET `/flame/api/admin/product`

根据管理端已有商品数据中的 `image_url` 读取奖品图片，不查询 `product` 表。

请求示例：

```http
GET /flame/api/admin/product?image_url=%2FKeep%20%E5%BC%B9%E5%8A%9B%E5%B8%A6.webp
```

Query 参数：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `image_url` | `string` | 是 | 奖品图片地址，例如 `/Keep 弹力带.webp`；应使用 URL 编码传递 |

后端会去除地址开头的 `/` 或 `\\`，拼接到 `assets/images/product`，并校验最终路径没有逃逸出奖品图片目录。响应类型根据文件扩展名自动识别。

成功响应示例：

```http
Content-Type: image/webp
Cache-Control: private, no-store
```

错误响应：

| 状态码 | 场景 | `detail` |
| --- | --- | --- |
| `400` | 图片地址为空或仅包含空白 | `商品图片路径不能为空` |
| `400` | 图片地址逃逸出奖品图片目录 | `商品图片路径非法` |
| `404` | 奖品图片文件不存在 | `奖品图片文件不存在` |
| `422` | 缺少 `image_url` | FastAPI 参数校验错误 |

---

## POST `/flame/api/admin/product/replace`

该接口同时接收新奖品图片、新地址和可选的旧地址。服务端先将新图片原子写入 `assets/images/product`，再清理不同地址下的旧文件。接口不修改 `product` 表，调用方应使用响应中的 `image_url` 完成奖品记录更新。

请求类型：

```http
Content-Type: multipart/form-data
```

字段说明：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| `old_image_url` | `string \| null` | 否 | 原奖品图片地址；缺省、空字符串或纯空白表示首次新建 |
| `new_image_url` | `string` | 是 | 新图片的最终相对地址，后缀必须为 `.jpg`、`.jpeg`、`.png` 或 `.webp` |
| `image` | `File` | 是 | 待存储的 JPEG、PNG 或 WebP 图片，最大 5 MiB |

请求示例：

```bash
curl -X POST 'http://backend:8000/flame/api/admin/product/replace' \
  -F 'old_image_url=/旧奖品.webp' \
  -F 'new_image_url=/新奖品.webp' \
  -F 'image=@./新奖品.webp;type=image/webp'
```

成功响应：

```json
{
  "image_url": "/新奖品.webp",
  "size_bytes": 185420,
  "old_image_removed": true
}
```

处理规则：

1. 校验新旧地址没有逃逸出 `assets/images/product`。
2. 校验文件媒体类型、实际图片格式和 `new_image_url` 后缀一致。
3. 图片为空、超过 5 MiB 或无法解码时立即失败，不改变旧图片。
4. 新图片使用同目录临时文件写入，完成后原子替换到新地址。
5. `old_image_url` 为空时直接创建新图片，`old_image_removed` 为 `false`。
6. 新旧地址指向同一文件时原子覆盖原文件，不执行删除。
7. 旧文件已不存在时仍返回成功，便于调用方安全重试。
8. 旧文件存在且与新地址不同时，新图写入成功后删除旧文件。

> **警告**
>
> 该接口会删除不同地址下的旧图片文件。如果多个奖品共用同一旧地址，调用前必须确认其他记录已不再引用该文件。

错误响应：

| 状态码 | 场景 | `detail` |
| --- | --- | --- |
| `400` | 新旧地址逃逸出奖品图片目录 | `商品图片路径非法` |
| `400` | 媒体类型、地址后缀或实际图片格式不匹配 | 对应的格式校验提示 |
| `400` | 上传文件为空或无法解码 | `奖品图片不能为空` 或 `上传内容不是有效的奖品图片` |
| `413` | 上传图片超过 5 MiB | `奖品图片不能超过 5 MiB` |
| `422` | 缺少新地址或图片，或地址字段超长 | FastAPI 参数校验错误 |

---

## GET `/flame/api/admin/proof_record/{proof_record_id}`

根据凭证记录 ID 查询有效凭证，并通过关联的赛季定位图片文件。该接口不校验凭证所属用户，供管理端查看不同用户的运动记录。

请求示例：

```http
GET /flame/api/admin/proof_record/115
```

定位关系：

```text
proof_record.id = proof_record_id
proof_record.season_user_id = season_user.id
season_user.season_id = season.id
proof_record.status = 1
```

最终文件路径：

```text
assets/images/proof_record/{season.id}/{proof_record.image_url}
```

该接口不要求赛季处于激活状态，因此管理端可以读取结算中赛季的凭证图片。调用方也不需要提供用户 ID 或赛季 ID；接口仍会校验凭证有效状态、赛季关联和文件路径安全。

成功响应示例：

```http
Content-Type: image/webp
Cache-Control: private, no-store
```

错误响应：

| 状态码 | 场景 | `detail` |
| --- | --- | --- |
| `404` | 凭证不存在、已失效或赛季关联不存在 | `凭证不存在` |
| `404` | 凭证缺少有效赛季主键 | `凭证所属赛季不存在` |
| `400` | 凭证图片路径逃逸出凭证目录 | `凭证图片路径非法` |
| `404` | 凭证图片文件不存在 | `凭证图片文件不存在` |
