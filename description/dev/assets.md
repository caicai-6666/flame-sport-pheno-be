# 本地资源目录说明

## 根目录

```text
assets/
  images/
    avatar/
    project_icon/
    proof_record/
```

## avatar

用户头像目录：

```text
assets/images/avatar
```

读取规则：

```text
settings.AVATAR_IMAGE_DIR / user.avatar_url
```

## project_icon

项目图标目录：

```text
assets/images/project_icon
```

项目列表接口会读取 `project.icon_url` 对应文件，并返回 base64 字符串。

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

## 路径安全

头像、项目图标和凭证图片读取时都应确保路径没有逃逸出对应资源目录。
