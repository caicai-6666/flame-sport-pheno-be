



# 项目规则表：project_rule

## 表作用
`project_rule` 表用于存储不同项目在不同挑战等级下的完成规则。
当前平台中，用户在一个赛季中选择 3 个运动项目，并选择一个统一的项目等级。  
系统根据用户选择的项目和等级，找到对应的项目规则，用于前端展示和月末审核判断。

该表只描述挑战规则本身，不记录用户数据，不记录赛季数据，也不记录积分。  
积分由 `project_level` 表中的等级积分字段决定。

当前设计中，项目规则是平台通用规则，不随赛季变化。

---

## 字段说明

| 字段名       | 类型             | 是否必填 | 默认值 | 说明                                 |
| ------------ | ---------------- | -------: | -----: | ------------------------------------ |
| id           | BIGINT UNSIGNED  |       是 |   自增 | 项目规则主键 ID                      |
| project_id   | BIGINT UNSIGNED  |       是 |     无 | 项目 ID，关联 `project.id`           |
| level_id     | BIGINT UNSIGNED  |       是 |     无 | 项目等级 ID，关联 `project_level.id` |
| rule_content | TEXT             |       是 |     无 | 规则内容说明                         |
| status       | TINYINT UNSIGNED |       是 |      1 | 规则状态：`1` 启用，`0` 停用         |

---

## 字段设计说明

### id

项目规则的唯一标识。

使用 `BIGINT UNSIGNED AUTO_INCREMENT` 作为主键。

---

### project_id

项目 ID。

该字段关联 `project.id`，表示这条规则属于哪个运动项目。

示例：

```text
日常步数
跑步/快走
健身打卡
减重挑战
```

---

### level_id

项目等级 ID。

该字段关联 `project_level.id`，表示这条规则对应哪个挑战等级。

示例：

```text
青铜
白银
黄金
```

---

### rule_content

规则内容说明。

用于描述某个项目、某个等级下需要完成的挑战要求。

示例：

```text
每日步数达到 8000 步，累计达标 20 天。
累计跑步或快走 50km，平均配速不高于 8'00''。
月初和月末各上传一次体重记录，并完成 BMI 下降目标。
```

当前平台采用月末统一人工审核模式，因此规则内容先以文本形式存储即可。  
审核人员根据用户上传的凭证和该规则内容判断是否达标。

---

### status

项目规则状态。

取值说明：

```text
1 = 启用
0 = 停用
```

保留该字段的原因是：规则一旦被用户选择、前端展示或历史审核引用，不建议物理删除。  
如果某条规则后续不再使用，可以将其状态改为停用。

---

## MySQL 建表语句

```sql
CREATE TABLE project_rule (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '项目规则ID',
  project_id BIGINT UNSIGNED NOT NULL COMMENT '项目ID',
  level_id BIGINT UNSIGNED NOT NULL COMMENT '项目等级ID',
  rule_content TEXT NOT NULL COMMENT '规则内容说明',
  status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态：1启用，0停用',
  PRIMARY KEY (id),
  UNIQUE KEY uk_project_rule_project_level (project_id, level_id),
  KEY idx_project_rule_project_id (project_id),
  KEY idx_project_rule_level_id (level_id),
  KEY idx_project_rule_status (status),
  CONSTRAINT fk_project_rule_project
    FOREIGN KEY (project_id) REFERENCES project(id),
  CONSTRAINT fk_project_rule_level
    FOREIGN KEY (level_id) REFERENCES project_level(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目规则表';
```