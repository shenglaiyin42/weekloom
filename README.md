# Weekloom（周织）

> 把项目织进每一周。

Weekloom 是一个面向个人使用的每周计划、GTD、项目推进与复盘系统。它把长期项目转化为每周可执行的行动，并通过本地网页应用、结构化数据、Excel 仪表盘和 GitHub 版本历史形成一个可持续使用的个人工作流。

## 当前阶段

项目正在进行 MVP 设计与初始化。当前基线见 [docs/product-baseline.md](docs/product-baseline.md)。私人数据目录和同步边界见 [docs/private-data-setup.md](docs/private-data-setup.md)。

下一阶段将定义五个核心数据模型：

- Project
- Action
- Week
- Inbox Item
- Review

数据模型已经落地，字段说明见 [docs/data-model.md](docs/data-model.md)，schema 位于 `schemas/`。

## 本地 MVP

```bash
python scripts/init_private_data.py
python app/server.py
```

打开 <http://127.0.0.1:8787> 即可查看当前周、更新行动、收集 Inbox 和保存周复盘。真实数据默认写入被忽略的 `.weekloom-data/`，也可以用 `WEEKLOOM_DATA_DIR` 指向独立私人目录。

运行基础测试：

```bash
python -m unittest discover -s tests -v
python scripts/validate_data.py --data-dir examples/data
```

## 产品原则

- 首先服务于个人实际使用，不追求一开始成为通用效率产品。
- 围绕“随时收集 → 每周选择 → 拆解行动 → 日常更新 → 每周复盘”设计。
- JSON 是唯一真实数据源；Excel 是生成的分析和导出物。
- 本地优先、离线可用，保存与 GitHub 同步相互独立。
- 公开代码与私人数据严格分离。
- MVP 不依赖 OpenAI API，不在浏览器前端保存 API key。

## 仓库结构

```text
weekloom/
├── app/                 # 本地网页应用
├── docs/                # 产品和开发文档
├── examples/data/       # 匿名示例数据
├── schemas/             # 数据模型与 JSON Schema
├── scripts/             # 数据验证和导出脚本
├── exports/             # 本地生成的 Excel 等导出物
├── .gitignore
└── README.md
```

## 数据与隐私

这是一个公开代码仓库，只允许提交代码、文档、数据格式和匿名示例数据。

真实的项目、工作计划、个人生活事项和周复盘必须保存在仓库外部的私人数据目录或独立 private repository 中。本地应用未来通过 `WEEKLOOM_DATA_DIR` 指向该目录。

请勿提交：

- 真实个人数据
- `.env` 或本地配置
- API key、访问令牌或其他凭据
- 本地生成的 Excel 导出文件

## GitHub

公开仓库：[shenglaiyin42/weekloom](https://github.com/shenglaiyin42/weekloom)
