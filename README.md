# Seed Scanner

加密货币助记词图片扫描工具 / Cryptocurrency Seed Phrase Scanner

## 功能

- 递归扫描目录中的图片文件
- 使用 PaddleOCR 离线识别图片文字
- 检测 12/24 词助记词（支持模糊匹配）
- 双哈希去重（文件哈希 + 感知哈希）
- 生成 JSON/TXT 报告
- 邮件发送扫描结果

## 安装

```bash
# 克隆仓库
git clone <repo>
cd seed-scanner

# 安装依赖
uv sync
```

## 配置

复制配置模板并编辑：

```bash
cp config.yaml.example config.yaml
nano config.yaml
```

## 使用

```bash
# 扫描目录
uv run python -m src.main /path/to/images

# 使用指定配置
uv run python -m src.main /path/to/images --config config.yaml

# 强制重新扫描
uv run python -m src.main /path/to/images --force

# 不发送邮件
uv run python -m src.main /path/to/images --no-mail
```

## 输出

扫描结果保存在 `output/` 目录：
- `scan_result_YYYYMMDD_HHMMSS.json` - 结构化数据
- `scan_result_YYYYMMDD_HHMMSS.txt` - 人类可读报告

## 安全提示

⚠️ 本工具处理敏感的助记词信息，请注意：
- 扫描结果文件包含助记词，请妥善保管
- 数据库文件 `data/seed_scanner.db` 缓存了 OCR 结果
- 建议扫描完成后清理输出文件
