# 图片接口

## 路由前缀

```text
/flame/api/image
```

---

## 接口列表

当前路由提供以下接口。

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/flame/api/image` | 否 | 图片子路由存活校验 |
| `GET` | `/flame/api/image/poster` | 是 | 获取当前活动海报 WebP 图片 |
| `GET` | `/flame/api/image/avatar` | 是 | 获取当前用户头像图片 |
| `GET` | `/flame/api/image/product` | 是 | 获取指定商品图片 |
| `GET` | `/flame/api/image/project_icon` | 是 | 获取指定项目图标 |
| `GET` | `/flame/api/image/proof_record/{proof_record_id}` | 是 | 获取当前用户自己的凭证图片 |

---

## 通用鉴权

业务接口需要请求头：

```http
Authorization: auth_code
```

---

## 图片缓存

头像、商品图片和项目图标响应都会设置：

```http
Cache-Control: private, max-age={IMAGE_CACHE_MAX_AGE_SECONDS}
```

默认值为 `604800`（7 天）。图片接口需要登录态，因此缓存限定为当前浏览器私有缓存，代理和 CDN 等共享缓存不得复用响应。

---

## GET `/flame/api/image`

成功响应：

```json
{
  "code": 200
}
```

---

## GET `/flame/api/image/poster`

返回固定资源 `assets/images/poster/活动规则.webp`。客户端不能传入文件名或本地路径，避免通过图片接口读取其他资源。

请求示例：

```http
GET /flame/api/image/poster
Authorization: auth_code
```

成功响应：

```http
Content-Type: image/webp
Cache-Control: private, no-cache
```

海报使用固定 URL 且允许管理端覆盖，因此浏览器每次读取都会向服务端确认资源是否更新，避免长期缓存旧海报。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| `401` | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| `404` | 固定海报文件不存在 | `活动海报文件不存在` |

---

## GET `/flame/api/image/avatar`

处理流程：

1. 从 `Authorization` 解析当前用户 ID。
2. 查询 `user` 表。
3. 读取 `user.avatar_url`。
4. 去掉路径前导斜杠后，拼接到本地头像目录 `assets/images/avatar`。
5. 返回头像文件。

成功响应：

```http
Content-Type: image/webp
```

用户头像统一返回 `image/webp`。

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 404 | 用户不存在 | `用户不存在` |
| 404 | 用户未配置头像 | `用户未配置头像` |
| 400 | 头像路径非法 | `头像路径非法` |
| 404 | 头像文件不存在 | `头像文件不存在` |

---

## GET `/flame/api/image/product`

请求示例：

```http
GET /flame/api/image/product?filename=%2FKeep%20%E5%BC%B9%E5%8A%9B%E5%B8%A6.webp
Authorization: auth_code
```

处理流程：

1. 从 `Authorization` 解析当前用户 ID。
2. 读取 query 参数 `filename`。
3. 去掉前导 `/` 或 `\`。
4. 拼接到本地商品图片目录 `assets/images/product`。
5. 校验路径没有逃逸出商品图片目录。
6. 返回商品图片文件。

前端应使用 `encodeURIComponent(image_url)` 生成 `filename` 参数。

成功响应：

```http
Content-Type: image/webp
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 400 | 商品图片路径为空 | `商品图片路径不能为空` |
| 400 | 商品图片路径非法 | `商品图片路径非法` |
| 404 | 商品图片不存在 | `商品图片文件不存在` |

---

## GET `/flame/api/image/project_icon`

请求示例：

```http
GET /flame/api/image/project_icon?filename=%2F%E8%B7%91%E6%AD%A5.webp
Authorization: auth_code
```

该接口接收项目列表返回的 `image` 值。后端会去掉前导 `/` 或 `\`，兼容移除历史 `/project_icon/` 前缀后，将其拼接到本地目录 `assets/images/project_icon`，校验路径安全后直接返回图片文件，不进行 Base64 编码。

前端应使用 `encodeURIComponent(image)` 生成 `filename` 参数。

成功响应示例：

```http
Content-Type: image/webp
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 400 | 项目图标路径为空 | `项目图标路径不能为空` |
| 400 | 项目图标路径非法 | `项目图标路径非法` |
| 404 | 项目图标不存在 | `项目图标文件不存在` |

---

## GET `/flame/api/image/proof_record/{proof_record_id}`

请求示例：

```http
GET /flame/api/image/proof_record/18
Authorization: auth_code
```

该接口仅用于读取 `GET /flame/api/proof/current` 和 `GET /flame/api/proof/history` 返回的 `imageUrl`。后端会按 `proof_record.id`、有效状态、当前登录用户归属和赛季可见状态查询凭证，再根据所属赛季定位图片文件；不会信任客户端传入的文件名或赛季目录。

客户端可以读取 `season.status = 1` 的进行中赛季、`status = 2` 的结算中赛季和 `status = 3` 的已结束赛季凭证图片，确保当前列表和历史列表中的 `imageUrl` 均可访问。未开始赛季的凭证不会通过客户端图片接口返回；管理端凭证图片接口不受该限制。

成功响应示例：

```http
Content-Type: image/webp
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 404 | 凭证不存在、已失效、不属于当前用户或赛季对客户端不可见 | `凭证不存在` |
| 400 | 凭证图片路径非法 | `凭证图片路径非法` |
| 404 | 凭证图片文件不存在 | `凭证图片文件不存在` |
