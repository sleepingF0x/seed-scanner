# 图片助记词扫描工具设计文档

## 目标

开发一个离线工具，递归扫描服务器目录中的图片，使用 OCR 识别文字内容，检测并提取加密货币助记词（12/24 个英文单词），输出结果并通过邮件发送。

## 架构

采用模块化设计，各组件职责单一，通过主程序协调。使用 SQLite 持久化已处理文件记录，避免重复 OCR。双哈希机制（文件哈希 + 感知哈希）实现精确去重和相似图片检测。

## 技术栈

- **OCR**: PaddleOCR（轻量版，纯离线）
- **数据库**: SQLite3
- **图像哈希**: imagehash (pHash)
- **配置**: PyYAML
- **邮件**: smtplib (SMTP)
- **CLI**: argparse

## 项目结构

```
seed_scanner/
├── src/
│   ├── __init__.py
│   ├── main.py           # CLI 入口，协调各模块
│   ├── config.py         # 配置加载（YAML + 命令行覆盖）
│   ├── scanner.py        # 目录递归扫描，图片文件过滤
│   ├── db.py             # SQLite 数据库操作
│   ├── hasher.py         # 文件哈希 + 感知哈希计算
│   ├── ocr_engine.py     # PaddleOCR 封装
│   ├── seed_detector.py  # 助记词检测（BIP39 词库匹配）
│   ├── reporter.py       # JSON/TXT 报告生成
│   └── mailer.py         # SMTP 邮件发送
├── data/
│   ├── seed_scanner.db       # SQLite 数据库
│   └── bip39_wordlist.txt    # BIP39 英文单词表
├── output/                   # 扫描结果输出目录
├── config.yaml               # 用户配置文件模板
├── pyproject.toml            # 项目依赖
└── README.md
```

## 数据流

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   目录扫描   │───▶│  双哈希计算  │───▶│  数据库查询  │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                             │
                              ┌──────────────┴──────────────┐
                              ▼                             ▼
                        ┌──────────┐                 ┌──────────┐
                        │ 已存在   │                 │ 新图片   │
                        │ 跳过OCR  │                 │ 继续处理 │
                        └──────────┘                 └────┬─────┘
                                                          ▼
                                                   ┌─────────────┐
                                                   │  PaddleOCR  │
                                                   │   文字识别   │
                                                   └──────┬──────┘
                                                          ▼
                                                   ┌─────────────┐
                                                   │ 助记词检测   │
                                                   │ 精确+模糊   │
                                                   └──────┬──────┘
                                                          ▼
                                                   ┌─────────────┐
                                                   │  结果入库   │
                                                   └─────────────┘
```

## 数据库设计

```sql
CREATE TABLE processed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,              -- SHA256 文件内容哈希
    phash TEXT NOT NULL,                  -- 感知哈希（16进制字符串）
    file_path TEXT NOT NULL,              -- 文件完整路径
    file_size INTEGER,                    -- 文件大小（字节）
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ocr_text TEXT,                        -- OCR 识别的完整文字（缓存）
    has_seed BOOLEAN DEFAULT 0,           -- 是否检测到助记词
    seed_phrase TEXT                      -- 检测到的助记词（如有）
);

CREATE INDEX idx_file_hash ON processed_files(file_hash);
CREATE INDEX idx_phash ON processed_files(phash);
CREATE INDEX idx_has_seed ON processed_files(has_seed);
```

## 去重策略

### 第一层：文件哈希（SHA256）
- 对文件二进制内容计算 SHA256
- 检测完全相同的文件（拷贝、复制）
- 速度：快（只需读取文件）

### 第二层：感知哈希（pHash）
- 基于图像视觉特征的 64-bit 哈希
- 检测相似图片（压缩、裁剪、调整亮度后的同一张图）
- 使用汉明距离判断相似度，阈值设为 5

### 去重流程
```python
def should_skip(image_path, db):
    # 1. 文件哈希检查
    file_hash = calc_sha256(image_path)
    if db.exists(file_hash=file_hash):
        return True, "exact_duplicate"

    # 2. 感知哈希检查
    phash = calc_phash(image_path)
    if db.exists_phash_similar(phash, threshold=5):
        return True, "similar_duplicate"

    return False, None
```

## 助记词检测算法

### 精确匹配
1. OCR 结果按空白字符分割成单词列表
2. 滑动窗口提取连续 12/24 个单词
3. 每个单词在 BIP39 词库中查找
4. 全部匹配则认为检测到助记词

### 模糊匹配（容错）
- OCR 可能识别错误：`abandon` → `aband0n`、`word` → `w0rd`
- 对不在词库中的单词，计算与 BIP39 所有词的编辑距离
- 距离 <= 1 且单词长度 >= 4 认为是该词
- 容错后仍满足 12/24 个有效词则命中

## 配置设计

```yaml
# config.yaml
scanner:
  supported_formats: [".png", ".jpg", ".jpeg", ".bmp", ".webp"]
  recursive: true

ocr:
  use_gpu: false
  lang: "en"  # 助记词都是英文

detection:
  seed_lengths: [12, 24]  # 检测 12 词或 24 词助记词
  fuzzy_threshold: 1      # 模糊匹配最大编辑距离

mail:
  enabled: true
  smtp_server: "smtp.qq.com"
  smtp_port: 587
  username: "your_email@qq.com"
  password: "your_auth_code"
  to_address: "recipient@example.com"
  subject: "助记词扫描结果"

output:
  directory: "./output"
  generate_json: true
  generate_txt: true
```

## 命令行接口

```bash
# 基本使用
python -m src.main /path/to/scan

# 指定配置文件
python -m src.main /path/to/scan --config ./config.yaml

# 强制重新扫描（忽略数据库记录）
python -m src.main /path/to/scan --force

# 只生成报告，不扫描
python -m src.main --report-only
```

## 安全考虑

1. **本地处理**: 所有 OCR 和检测在本地完成，助记词不上传云端
2. **敏感数据**: 助记词只在报告中展示，不打印到控制台日志
3. **文件权限**: 数据库和输出目录设置合理权限（600/700）
4. **邮件安全**: 使用 TLS 加密 SMTP 连接

## 扩展性

- OCR 引擎可替换：ocr_engine.py 定义统一接口
- 检测算法可扩展：seed_detector 支持添加新的检测模式
- 通知方式可扩展：mailer.py 可扩展支持钉钉、企业微信等
