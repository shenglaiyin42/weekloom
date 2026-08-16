# App

本目录用于 Weekloom 的本地网页应用。

应用将运行在 `localhost` 中，主要负责日常录入、每周规划、行动更新和周复盘。真实数据目录不会位于本公开仓库内，后续通过 `WEEKLOOM_DATA_DIR` 配置连接。

## 运行 MVP

```bash
python scripts/init_private_data.py
python app/server.py
```

然后打开 <http://127.0.0.1:8787>。默认数据写入被 `.gitignore` 忽略的 `.weekloom-data/`；也可以通过 `WEEKLOOM_DATA_DIR` 指定独立的私人数据目录。

当前页面支持：

- 查看当前周、核心成果、项目和本周行动。
- 创建项目。
- 创建行动并加入当前周，可指定项目、优先级、本周角色和下一步。
- 更新行动状态。
- 快速新增 Inbox 项目。
- 填写并保存周复盘。
- 生成私人数据目录中的 Codex 复盘请求。
- 查看私人数据目录的本地 Git 同步状态。
