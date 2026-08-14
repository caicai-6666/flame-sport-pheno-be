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

---

## avatar

用户头像目录：

```text
assets/images/avatar
```

首次钉钉登录初始化时，如钉钉返回头像地址，服务端会下载 JPEG、PNG 或 WebP 图片并统一转换为不超过 300 KiB 的 WebP。文件名为安全化后的钉钉 `userId` 加小写 `.webp`，例如：

```text
james.webp
```

`user.avatar_url` 保存带前导斜杠的相对路径，例如：

```text
/james.webp
```

转换会修正 EXIF 方向并保留透明通道；编码时优先降低 WebP 质量，仍超过限制时再逐步缩小像素尺寸。文件使用原子写入，如果后续用户初始化事务失败，则恢复覆盖前的头像或删除本次新文件。

现有用户头像已使用以下脚本迁移为 WebP。脚本复用新用户头像的质量与缩放策略，将单图控制在 300 KiB 内；转换前会备份原图，验证新文件后才删除旧扩展名文件：

```bash
python scripts/convert_avatar_images_to_webp.py \
  --source-dir assets/images/avatar \
  --backup-dir assets/backups/avatar_before_webp_YYYYMMDD
```

文件转换完成后执行 `scripts/migrations/20260814_convert_user_avatar_urls_to_webp.sql`，同步更新 `user.avatar_url`。生产环境使用 Docker 具名卷时，应先暂停新用户初始化，对 `/app/assets/images/avatar` 执行转换，再运行数据库迁移。

读取时会去除前导斜杠，再拼接目录：

```text
settings.AVATAR_IMAGE_DIR / user.avatar_url.lstrip("/")
```

---

## project_icon

项目图标目录：

```text
assets/images/project_icon
```

项目列表接口直接返回 `project.icon_url` 保存的相对地址，例如 `/跑步.webp`。前端再通过：

```text
GET /flame/api/image/project_icon?filename={encodeURIComponent(project.image)}
```

读取对应图片文件。

新图标可通过以下接口写入：

```text
POST /flame/api/admin/project_icon
```

该写入接口仅通过 Docker 内部的 `admin` 路由管理端调用。接口接受 JPEG、PNG 或 WebP，但 `icon_url` 必须以 `.webp` 结尾；服务端校验最长边不超过 1600 像素后，在线程池中无损编码为 WebP，并使用同目录临时文件原子替换目标文件。上传限制为 5 MiB。

现有项目图标可通过以下脚本无损转换。脚本会先保留原目录结构备份，再删除旧扩展名文件：

```bash
python scripts/convert_project_icons_to_webp.py \
  --source-dir assets/images/project_icon \
  --backup-dir assets/backups/project_icon_before_webp_YYYYMMDD
```

转换完成后执行 `scripts/migrations/20260814_convert_project_icon_urls_to_webp.sql`，同步更新 `project.icon_url`。生产环境使用 Docker 具名卷时，应先暂停项目图标写入，对 `/app/assets/images/project_icon` 执行转换，再运行数据库迁移。

由于读取接口存在浏览器缓存，更换图标时应优先使用新的唯一文件名，避免同一 `icon_url` 覆盖后客户端继续显示旧图。

---

## product

商品图片目录：

```text
assets/images/product
```

商城信息接口只返回 `product.image_url` 字符串，不返回图片文件。

示例：

```text
/Keep 弹力带.webp
```

前端请求商品图片时应使用：

```text
GET /flame/api/image/product?filename={encodeURIComponent(product.image_url)}
```

后端会去掉前导 `/` 或 `\`，再拼接到 `settings.PRODUCT_IMAGE_DIR`。

管理端已取得商品的 `image_url` 后，可通过 Docker 内部接口读取同一目录中的奖品图片：

```text
GET /flame/api/admin/product?image_url={encodeURIComponent(product.image_url)}
```

管理端可通过以下接口上传并替换奖品图片：

```text
POST /flame/api/admin/product/replace
```

该接口使用 `multipart/form-data` 同时接收新图片、新地址和可选的旧地址。服务端校验 JPEG、PNG 或 WebP 内容后先原子写入新图，再删除不同地址下的旧图片。旧地址为空时按首次新建处理；旧文件已不存在时也允许安全重试。该接口不修改 `product.image_url`，数据库记录由管理端业务接口单独更新。

当前商品图已统一使用 WebP，既能显著减小传输体积，也能保留原 PNG 图片的透明通道。批量转换脚本保持原始像素尺寸，默认使用质量 82；转换前会将 JPEG、PNG 原图备份到 `assets/backups/`，确认新文件可以正常解码后才删除旧扩展名文件。

本地转换命令：

```bash
python scripts/convert_product_images_to_webp.py \
  --source-dir assets/images/product \
  --backup-dir assets/backups/product_before_webp_YYYYMMDD
```

转换后还需要执行 `scripts/migrations/20260813_convert_product_image_urls_to_webp.sql`，同步更新 `product.image_url`，否则接口仍会按旧扩展名定位图片。

对于已经写入 Docker 具名卷的生产图片，可将脚本复制进正在运行的后端容器后执行：

```bash
docker cp scripts/convert_product_images_to_webp.py flame-sport-pheno-backend-1:/tmp/
docker exec flame-sport-pheno-backend-1 python /tmp/convert_product_images_to_webp.py \
  --source-dir /app/assets/images/product \
  --backup-dir /app/assets/backups/product_before_webp_YYYYMMDD
```

---

## proof_record

凭证图片目录：

```text
assets/images/proof_record/{season_id}
```

上传接口生成的文件名：

```text
{user_id}-{project_id}-{timestamp}-{上传文件主名}.webp
```

数据库当前只保存完整文件名，例如：

```text
bb123456-3-20260606090020-健身.webp
```

上传接口接受 JPEG、PNG 或 WebP 图片，并在服务端按质量 82 统一重编码为 WebP。转换保持原始像素尺寸，修正 EXIF 方向并支持透明通道；最终文件使用原子写入，数据库事务失败时会清理新文件。

历史图片转换前会按原有赛季目录结构备份原图。开发环境执行：

```bash
python scripts/convert_proof_record_images_to_webp.py \
  --source-dir assets/images/proof_record \
  --backup-dir assets/backups/proof_record_before_webp_YYYYMMDD
```

文件转换成功后，执行 `scripts/migrations/20260813_convert_proof_record_image_urls_to_webp.sql`，同步更新 `proof_record.image_url`。生产环境应先暂停凭证上传，再对 `/app/assets/images/proof_record` 所在具名卷执行相同转换，最后运行数据库迁移，避免文件名和数据库地址短暂不一致。

确认激活赛季时会自动创建对应的 `{season_id}` 子目录；上传时会再次检查，以支持资源目录被运维清理后的恢复。

---

## 路径安全

头像、项目图标、商品图片和凭证图片读取时都应确保路径没有逃逸出对应资源目录。
