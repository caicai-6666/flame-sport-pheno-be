# 商城业务说明

## 业务目标

商城用于展示当前可兑换商品，并支持用户使用积分兑换商品。当前兑换只写入积分扣减流水，不处理库存、订单或独立兑换记录表。

---

## 商品列表

当前商品列表接口：

```text
GET /flame/api/shop/product_info
```

接口查询 `product.status = 1` 的可见商品，并返回：

```text
id
name
description
points_required
image_url
```

该接口不返回真实图片文件。前端拿到 `image_url` 后，再请求 `/flame/api/image/product` 获取图片。

---

## 商品图片

商品图片统一放在：

```text
assets/images/product
```

数据库 `product.image_url` 可以保存文件名或相对路径。当前商品数据保存类似：

```text
/Keep 弹力带.webp
```

现有商品图片统一使用 WebP，以减小商城列表的图片传输体积，并保留原 PNG 图片的透明通道。图片读取时，后端会去掉前导 `/` 或 `\`，再拼接到商品图片目录，并校验路径没有逃逸出该目录。

前端请求示例：

```text
GET /flame/api/image/product?filename={encodeURIComponent(product.image_url)}
```

---

## 积分流水

当前积分流水接口：

```text
GET /flame/api/shop/point_flow
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

---

## 商品兑换

当前商品兑换接口：

```text
POST /flame/api/shop/consume
```

请求体传入：

```text
product_id
```

兑换流程：

1. 校验当前时间不在赛季开始后的配置保护期。
2. 查询商品并校验 `product.status = 1`。
3. 锁定当前用户的 `user` 行，串行化同一用户的积分扣减。
4. 查询当前用户最后一条有效积分流水，读取 `points_after` 作为当前积分余额。
5. 判断当前积分余额是否足够支付 `product.points_required`。
6. 积分足够时写入一条 `exchange` 类型的 `point_record`。

保护期使用 `ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS`，并按 `Asia/Shanghai` 的赛季开始日 `00:00` 起算；保护期内返回 `409` 且不产生积分流水。完整口径参见[赛季参与和项目锁定流程](season_project_flow.md#赛季开始配置保护期)。

写入流水：

```text
point_record.user_id = 当前登录用户 ID
point_record.product_id = product.id
point_record.change_type = exchange
point_record.change_points = -product.points_required
point_record.points_after = 当前积分余额 - product.points_required
point_record.description = 兑换商品：{product.name}
point_record.status = 1
point_record.gift_distribution_status = pending
```

`gift_distribution_status` 只记录兑换礼品是否已经发放，不影响本次积分扣减或 `points_after`。当前阶段只创建待发放流水，不处理库存、订单、独立兑换记录或管理端发放操作。
