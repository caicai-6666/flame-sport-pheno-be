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

本地直接运行时，资源位于后端仓库的 `assets/`。Docker Compose 部署时，该目录在容器内仍为 `/app/assets`，但实际由具名卷 `backend_assets` 持久化，以避免频繁拉取或重建后端工作区影响上传文件。

## avatar

用户头像目录：

```text
assets/images/avatar
```

首次钉钉登录初始化时，如钉钉返回头像地址，服务端会下载 JPEG、PNG 或 WebP 图片并统一转换为 JPEG。文件名为安全化后的钉钉 `userId` 加小写 `.jpg`，例如：

```text
james.jpg
```

`user.avatar_url` 保存带前导斜杠的相对路径，例如：

```text
/james.jpg
```

读取时会去除前导斜杠，再拼接目录：

```text
settings.AVATAR_IMAGE_DIR / user.avatar_url.lstrip("/")
```

## project_icon

项目图标目录：

```text
assets/images/project_icon
```

项目列表接口直接返回 `project.icon_url` 保存的相对地址，例如 `/跑步.png`。前端再通过：

```text
GET /flame/api/image/project_icon?filename={encodeURIComponent(project.image)}
```

读取对应图片文件。

## product

商品图片目录：

```text
assets/images/product
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
assets/images/proof_record/{season_id}
```

上传接口生成的文件名：

```text
{user_id}-{project_id}-{timestamp}-{上传文件主名}.jpg
```

数据库当前只保存完整文件名，例如：

```text
bb123456-3-20260606090020-健身.jpg
```

确认激活赛季时会自动创建对应的 `{season_id}` 子目录；上传时会再次检查，以支持资源目录被运维清理后的恢复。

## 路径安全

头像、项目图标、商品图片和凭证图片读取时都应确保路径没有逃逸出对应资源目录。
