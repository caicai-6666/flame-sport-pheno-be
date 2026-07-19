# health 接口文档

## 接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/` | 否 | 根路径健康检查 |
| GET | `/hello/{name}` | 否 | 测试路径参数 |

## GET /

成功响应：

```json
{
  "message": "Hello World"
}
```

## GET /hello/{name}

示例：

```http
GET /hello/flame
```

成功响应：

```json
{
  "message": "Hello flame"
}
```
