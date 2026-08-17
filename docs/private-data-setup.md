# 私人数据目录与 GitHub 同步

公开仓库 `shenglaiyin42/weekloom` 只保存代码、文档、schema 和匿名示例。真实项目、行动和复盘必须放在公开仓库之外。

## 本地目录

最简单的本地启动方式：

```bash
python3 scripts/init_private_data.py --target .weekloom-data
python3 app/server.py
```

`.weekloom-data/` 已被 `.gitignore` 忽略，不会进入公开代码仓库。

更稳妥的长期方式是把数据放到独立目录：

```bash
mkdir -p ~/WeekloomPrivateData
python3 scripts/init_private_data.py --target ~/WeekloomPrivateData
WEEKLOOM_DATA_DIR=~/WeekloomPrivateData python3 app/server.py
```

## 私人 GitHub 仓库

等确定仓库名称后，在 GitHub 创建 **private repository**，然后在私人数据目录中：

```bash
cd ~/WeekloomPrivateData
git init
git add .
git commit -m "chore: initialize private Weekloom data"
git branch -M main
git remote add origin <private-repository-url>
git push -u origin main
```

App 目前只读取本地 Git 状态，不会自动向远程 push。这样可以先确认数据目录、远程地址和身份验证都正确，再实现同步按钮。
