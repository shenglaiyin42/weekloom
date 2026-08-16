# Scripts

本目录保存数据验证、迁移、Excel 生成和其他本地维护脚本。

当前可用：

```bash
python scripts/validate_data.py --data-dir examples/data
```

校验脚本不依赖第三方 Python 包，并会同时检查 JSON 结构和实体之间的基本引用关系。
