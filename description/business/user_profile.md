# 用户资料业务说明

## 业务目标

用户资料接口用于维护当前登录用户的基础健康资料。当前阶段只支持设置身高，供资料完备性检查和后续 BMI 相关业务使用。

---

## 设置资料

当前设置接口：

```text
POST /flame/api/user/profile
```

请求体：

```text
height_cm
```

处理规则：

1. 从 `Authorization` 解析当前登录用户 ID。
2. 查询 `user` 表确认用户存在。
3. 校验 `height_cm` 范围为 50 到 300。
4. 将 `height_cm` 保留两位小数后写入 `user.height_cm`。

当前接口只更新身高，不修改认证缓存、不修改用户所属部门、不修改头像等其他基础信息。

身高更新不受赛季开始配置保护期限制，用户可以在保护期内继续完善或修正资料。

---

## 资料完备性

资料是否完整由以下接口判断：

```text
GET /flame/api/auth/profile_complete_check
```

当前完备性规则仍然只检查 `user.height_cm IS NOT NULL`。
