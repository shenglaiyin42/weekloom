# Weekloom 数据模型 v0.1

Weekloom 的第一版数据模型围绕五类实体建立：Project、Action、Week、Inbox Item 和 Review。

## 实体关系

```text
Project 1 ──── * Action
Week    1 ──── * Action
Week    1 ──── 1 Review
Inbox Item ────> Project / Action（整理后可选转换）
```

## 文件布局

真实数据目录（位于公开仓库之外）建议使用以下布局：

```text
private-data/
├── projects/*.json
├── actions/*.json
├── weeks/*.json
├── inbox/*.json
└── reviews/*.json
```

`examples/data/` 只保存匿名示例，公开仓库中的 JSON Schema 位于 `schemas/`。

## 设计约束

- 每个实体拥有稳定、可读的 `id`。
- 日期使用 `YYYY-MM-DD`，时间使用 ISO 8601 格式并带时区。
- 项目和行动分开保存，避免一个大型文件成为同步冲突中心。
- `category`、`priority` 和 `weekly_role` 是相互独立的维度。
- `next_action_id` 允许为空；应用需要提醒活跃项目补充下一步行动。
- 未完成行动在新周开始时需要重新确认，不自动承诺。
- schema 允许未来增加迁移版本，但当前实体字段保持明确和稳定。
