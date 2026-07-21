# 商城接口

## 接口概览

| 方法 | 路径 | 是否鉴权 | 说明 |
| --- | --- | ---: | --- |
| GET | `/api/shop/product_info` | 是 | 获取商城可见商品列表 |
| GET | `/api/shop/point_flow` | 是 | 获取当前用户积分流水 |
| POST | `/api/shop/consume` | 是 | 兑换商品并写入积分流水 |

---

## GET /api/shop/product_info

请求示例：

```http
GET /api/shop/product_info
Authorization: auth_code
```

成功响应：

```json
[
  {
    "id": 1,
    "name": "Keep 弹力带-入门款",
    "description": "适合热身、拉伸和基础力量训练。",
    "points_required": 30,
    "image_url": "/Keep 弹力带-入门款.jpg"
  }
]
```

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | number | 商品 ID |
| name | string | 商品名称 |
| description | string | 商品说明，数据库为空时返回空字符串 |
| points_required | number | 兑换该商品所需积分 |
| image_url | string | 商品图片路径，数据库为空时返回空字符串 |

数据来源：

```text
product.status = 1
```

该接口只返回商品元数据，不返回真实图片文件。前端拿到 `image_url` 后，应单独请求：

```http
GET /api/image/product?filename={encodeURIComponent(image_url)}
```

---

## GET /api/shop/point_flow

请求示例：

```http
GET /api/shop/point_flow
Authorization: auth_code
```

成功响应：

```json
[
  {
    "product_name": "Keep 弹力带-入门款",
    "change_type": "exchange",
    "change_points": -30,
    "points_after": 70,
    "description": "兑换商品：Keep 弹力带-入门款",
    "created_at": "2026-07-20T12:30:00"
  },
  {
    "product_name": "",
    "change_type": "season_reward",
    "change_points": 100,
    "points_after": 100,
    "description": "2026年7月赛季青铜挑战达标奖励",
    "created_at": "2026-07-19T18:00:00"
  }
]
```

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| product_name | string | 商品名称；非商品兑换流水返回空字符串 |
| change_type | string | 积分变动类型，例如 `season_reward`、`exchange`、`manual_adjust` |
| change_points | number | 本次积分变动值，正数增加，负数扣减 |
| points_after | number | 本次变动后的用户积分余额 |
| description | string | 积分变动描述，数据库为空时返回空字符串 |
| created_at | string | 积分变动时间，ISO 秒级格式 |

数据来源：

```text
point_record.user_id = 当前登录用户 ID
point_record.status = 1
point_record.product_id = product.id
```

该接口只返回当前登录用户的有效积分流水。商品关联使用左连接，因此 `product_id` 为空的奖励或人工调整流水也会返回。

接口不在后端排序，前端可以基于 `created_at` 自行决定展示顺序。

---

## POST /api/shop/consume

请求示例：

```http
POST /api/shop/consume
Authorization: auth_code
Content-Type: application/json
```

请求体：

```json
{
  "product_id": 1
}
```

请求字段：

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | ---: | --- |
| product_id | number | 是 | 要兑换的商品 ID，必须大于等于 1 |

成功响应：

```json
{
  "points_after": 70,
  "created_at": "2026-07-20T13:00:00"
}
```

处理流程：

1. 校验商品存在且 `product.status = 1`。
2. 锁定当前登录用户的 `user` 行，避免并发兑换超扣。
3. 查询当前用户最后一条有效积分流水，读取 `points_after` 作为当前积分余额。
4. 校验当前积分余额是否大于等于 `product.points_required`。
5. 写入一条 `point_record`：

```text
change_type = exchange
change_points = -product.points_required
points_after = 当前积分余额 - product.points_required
description = 兑换商品：{product.name}
status = 1
```

错误响应：

| 状态码 | 场景 | detail |
| --- | --- | --- |
| 401 | 未登录或登录过期 | `登录状态无效或已过期，请重新登录` |
| 404 | 商品不存在或已下架 | `商品不存在或已下架` |
| 404 | 用户不存在 | `用户不存在` |
| 409 | 积分不足 | `积分不足，无法兑换该商品` |

当前接口只处理积分扣减流水，不处理库存、订单或兑换记录表。
