# 商城业务说明

## 业务目标

商城用于展示当前可兑换商品，并支持用户使用积分兑换商品。当前兑换只写入积分扣减流水，不处理库存、订单或独立兑换记录表。

## 商品列表

当前商品列表接口：

```text
GET /api/shop/product_info
```

接口查询 `product.status = 1` 的可见商品，并返回：

```text
id
name
description
points_required
image_url
```

该接口不返回真实图片文件。前端拿到 `image_url` 后，再请求 `/api/image/product` 获取图片。

## 商品图片

商品图片统一放在：

```text
assets/api/images/product
```

数据库 `product.image_url` 可以保存文件名或相对路径。当前 mock 数据允许保存类似：

```text
/Keep 弹力带-入门款.jpg
```

图片读取时，后端会去掉前导 `/` 或 `\`，再拼接到商品图片目录，并校验路径没有逃逸出该目录。

前端请求示例：

```text
GET /api/image/product?filename={encodeURIComponent(product.image_url)}
```

## 积分流水

当前积分流水接口：

```text
GET /api/shop/point_flow
```

接口基于当前登录 `user_id` 查询 `point_record.status = 1` 的有效积分流水，并左连接 `product` 获取商品名称。

返回字段：

```text
product_name
change_type
change_points
points_after
description
created_at
```

非商品兑换流水的 `product_id` 为空，此时 `product_name` 返回空字符串。

积分流水接口不在后端排序，前端可以基于 `created_at` 自行决定展示顺序。

## 商品兑换

当前商品兑换接口：

```text
POST /api/shop/consume
```

请求体传入：

```text
product_id
```

兑换流程：

1. 查询商品并校验 `product.status = 1`。
2. 锁定当前用户的 `user` 行，串行化同一用户的积分扣减。
3. 查询当前用户最后一条有效积分流水，读取 `points_after` 作为当前积分余额。
4. 判断当前积分余额是否足够支付 `product.points_required`。
5. 积分足够时写入一条 `exchange` 类型的 `point_record`。

写入流水：

```text
point_record.user_id = 当前登录用户 ID
point_record.product_id = product.id
point_record.change_type = exchange
point_record.change_points = -product.points_required
point_record.points_after = 当前积分余额 - product.points_required
point_record.description = 兑换商品：{product.name}
point_record.status = 1
```

当前阶段只完成积分扣减流水写入，不处理库存、订单或兑换记录表。
