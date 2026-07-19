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
