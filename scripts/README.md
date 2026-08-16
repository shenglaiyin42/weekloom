# Scripts

本目录保存数据验证、迁移、Excel 生成和其他本地维护脚本。

当前可用：

```bash
python scripts/validate_data.py --data-dir examples/data
```

校验脚本不依赖第三方 Python 包，并会同时检查 JSON 结构和实体之间的基本引用关系。

生成 Excel 仪表盘：

```bash
python3 scripts/validate_data.py --data-dir .weekloom-data
node scripts/export_workbook.mjs --data-dir .weekloom-data --output exports/Weekloom.xlsx
```

`exports/Weekloom.xlsx` 是由私人数据生成的本地导出物，默认被 Git 忽略。
