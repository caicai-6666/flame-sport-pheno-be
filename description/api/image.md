# image 接口文档

## 路由前缀

```text
/image
```

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/image` | 否 | 图片子路由存活校验 |
| GET | `/image/avatar` | 是 | 获取当前用户头像图片 |
| GET | `/image/product` | 是 | 获取指定商品图片 |

## 通用鉴权

业务接口需要请求头：

```http
Authorization: auth_code
```

## GET /image

成功响应：

```json
{
  "code": 200
}
```

## GET /image/avatar

处理流程：

1. 从 `Authorization` 解析当前用户 ID。
2. 查询 `user` 表。
3. 读取 `user.avatar_url`。
4. 拼接到本地头像目录 `assets/images/avatar`。
5. 返回头像文件。

成功响应：

```http
Content-Type: image/jpeg
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 404 | 用户不存在 | `用户不存在` |
| 404 | 用户未配置头像 | `用户未配置头像` |
| 400 | 头像路径非法 | `头像路径非法` |
| 404 | 头像文件不存在 | `头像文件不存在` |

## GET /image/product

请求示例：

```http
GET /image/product?filename=%2FKeep%20%E5%BC%B9%E5%8A%9B%E5%B8%A6-%E5%85%A5%E9%97%A8%E6%AC%BE.jpg
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
Content-Type: image/jpeg
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 400 | 商品图片路径为空 | `商品图片路径不能为空` |
| 400 | 商品图片路径非法 | `商品图片路径非法` |
| 404 | 商品图片不存在 | `商品图片文件不存在` |
