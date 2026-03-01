# Seed Scanner

加密货币助记词图片扫描工具 / Cryptocurrency Seed Phrase Scanner

## 功能

- 递归扫描目录中的图片文件
- 使用 PaddleOCR 离线识别图片文字
- 检测 12/24 词助记词（支持模糊匹配）
- 双哈希去重（文件哈希 + 感知哈希）
- 生成 JSON/TXT 报告
- 邮件发送扫描结果

## 快速开始

### 本地开发

```bash
# 克隆仓库
git clone <your-repo-url>
cd seed-scanner

# 安装依赖
uv sync

# 复制配置
cp config.yaml.example config.yaml

# 运行扫描
uv run python -m src.main /path/to/images
```

## 部署方式

### 方式一：Docker Compose（推荐）

适用于 Ubuntu 服务器 + SMB 挂载目录扫描。

#### 1. 服务器准备

```bash
# SSH 登录服务器
ssh root@your-server-ip

# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 挂载 SMB 共享
mkdir -p /mnt/xspt
mount -t cifs //NAS_IP/share /mnt/xspt -o username=xxx,password=xxx
```

#### 2. 部署项目

```bash
# 克隆项目（私有仓库）
git clone <your-repo-url> /opt/seed-scanner
cd /opt/seed-scanner

# 配置环境变量
cp .env.example .env
vim .env
# 修改 SCAN_PATH=/mnt/xspt 为你的 SMB 挂载路径

# 构建并运行
docker-compose up --build
```

#### 3. 后续更新

```bash
cd /opt/seed-scanner
git pull
docker-compose up --build
```

#### 常用命令

```bash
# 立即扫描
docker-compose up

# 强制重新扫描（忽略缓存）
docker-compose run --rm seed-scanner /scan --force

# 后台运行
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止并删除容器/网络（保留 OCR 模型缓存 volume）
docker-compose down

# 停止并删除容器/网络/volume（会删除 OCR 模型缓存，后续会重新下载）
docker-compose down -v

# 定时扫描（添加 cron 任务）
crontab -e
# 添加: 0 */6 * * * cd /opt/seed-scanner && docker-compose up
```

## 配置说明

### config.yaml

```yaml
scanner:
  supported_formats: [".png", ".jpg", ".jpeg", ".bmp", ".webp"]
  recursive: true

ocr:
  use_gpu: false
  lang: "en"

detection:
  seed_lengths: [12, 24]
  fuzzy_threshold: 1

mail:
  enabled: false
  # 邮件配置...

output:
  directory: "./output"
  generate_json: true
  generate_txt: true
```

### .env（Docker 部署）

```bash
# 扫描目标目录（SMB 挂载点）
SCAN_PATH=/mnt/xspt

# 项目目录
PROJECT_PATH=/opt/seed-scanner

# 时区
TZ=Asia/Shanghai
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

部署说明以本 README 为准。

## 项目结构

```
seed-scanner/
├── src/              # 源代码
├── tests/            # 测试文件
├── data/             # BIP39 词库 & 数据库
├── output/           # 扫描结果输出
├── docs/             # 设计/计划文档
├── docker-compose.yml       # Docker 编排
├── Dockerfile               # Docker 镜像定义
├── .env.example             # 环境变量模板
├── config.yaml.example      # 配置文件模板
└── README.md
```
