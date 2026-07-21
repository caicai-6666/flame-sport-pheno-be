# 本地资源目录说明

## 根目录

```text
assets/
  images/
    avatar/
    product/
    project_icon/
    proof_record/
```

## avatar

用户头像目录：

```text
assets/api/images/avatar
```

读取规则：

```text
settings.AVATAR_IMAGE_DIR / user.avatar_url
```

## project_icon

项目图标目录：

```text
assets/api/images/api/project_icon
```

项目列表接口会读取 `project.icon_url` 对应文件，并返回 base64 字符串。

## product

商品图片目录：

```text
assets/api/images/product
```

商城信息接口只返回 `product.image_url` 字符串，不返回图片文件。

示例：

```text
/Keep 弹力带-入门款.jpg
```

前端请求商品图片时应使用：

```text
GET /api/image/product?filename={encodeURIComponent(product.image_url)}
```

后端会去掉前导 `/` 或 `\`，再拼接到 `settings.PRODUCT_IMAGE_DIR`。

## proof_record

凭证图片目录：

```text
assets/api/images/api/proof_record/{season_id}
```

上传接口生成的文件名：

```text
{user_id}-{project_id}-{timestamp}-{上传文件主名}.jpg
```

数据库当前只保存完整文件名，例如：

```text
bb123456-3-20260606090020-健身.jpg
```

## 路径安全

头像、项目图标、商品图片和凭证图片读取时都应确保路径没有逃逸出对应资源目录。
