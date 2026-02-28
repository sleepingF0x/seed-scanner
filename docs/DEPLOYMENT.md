# 部署指南 / Deployment Guide

## 快速开始

### 方式一：本地运行（已配置）

```bash
# 1. 确保依赖已安装
uv sync

# 2. 运行扫描
uv run python -m src.main /Volumes/xspt --config config.yaml
```

### 方式二：Docker 部署

```bash
# 构建并运行
docker-compose up -d

# 查看进度
docker-compose logs -f
```

---

## SMB 挂载注意事项

你的扫描目录 `/Volumes/xspt` 是通过 SMB 挂载的，需要注意：

### 1. 文件名编码问题

SMB 挂载可能包含各种语言文件名，已修复 scanner.py 来处理异常。

如果遇到编码错误，在 macOS 挂载时指定编码：
```bash
# 重新挂载 SMB，强制 UTF-8
sudo umount /Volumes/xspt
mount_smbfs //user@server/share /Volumes/xspt -o charset=utf-8
```

### 2. 网络延迟优化

```yaml
# config.yaml 建议配置
scanner:
  recursive: true
  # 如果目录很大，可以先测试非递归模式
  # recursive: false

database:
  # 使用本地数据库，不要放在 SMB 上
  path: "./data/seed_scanner.db"

output:
  # 输出到本地目录
  directory: "./output"
```

### 3. 权限问题

```bash
# 确保对挂载目录有读取权限
ls -la /Volumes/xspt

# 如果权限不足，尝试：
sudo chmod -R +r /Volumes/xspt
```

---

## 生产环境部署

### 服务器部署步骤

```bash
# 1. 准备服务器（Ubuntu/Debian）
sudo apt update
sudo apt install -y python3-pip python3-venv smbclient cifs-utils

# 2. 挂载 SMB 共享
sudo mkdir -p /mnt/xspt
sudo mount -t cifs //your-server/share /mnt/xspt \
  -o username=your_user,password=your_pass,charset=utf-8

# 3. 安装项目
git clone <repo-url>
cd seed-scanner
uv sync

# 4. 配置
cp config.yaml.example config.yaml
# 编辑 config.yaml

# 5. 使用 systemd 守护进程运行
sudo tee /etc/systemd/system/seed-scanner.service << 'EOF'
[Unit]
Description=Seed Scanner Service
After=network.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/seed-scanner
ExecStart=/usr/local/bin/uv run python -m src.main /mnt/xspt --config config.yaml
# 定时运行（每 6 小时）
# OnCalendar=*-*-* 00,06,12,18:00:00

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable seed-scanner
```

---

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` | 禁用模型检查加速启动 | `True` |
| `PADDLE_PDX_MODEL_ROOT` | 模型存储路径 | `~/.paddlex` |

---

## 性能优化

### 1. 首次运行会下载模型（约 100MB）

```bash
# 预下载模型（避免运行时等待）
python -c "from paddleocr import PaddleOCR; PaddleOCR()"
```

### 2. 大批量扫描优化

```yaml
# config.yaml
scanner:
  # 只扫描特定格式减少IO
  supported_formats: [".png", ".jpg", ".jpeg"]

ocr:
  # 如果准确率足够，可以跳过某些预处理
  use_gpu: false  # CPU 模式更稳定
```

### 3. 内存限制

PaddleOCR 默认占用较多内存，建议：
- 最小内存：2GB
- 推荐内存：4GB+

---

## 常见问题

### Q: SMB 挂载的文件名乱码？
A: 重新挂载指定编码 `charset=utf-8`

### Q: 扫描大量文件时卡住？
A: 使用 `--force` 跳过数据库检查，或增加内存限制

### Q: 邮件发送失败？
A: 检查 SMTP 配置，或使用 `--no-mail` 禁用

### Q: 如何定期自动扫描？
A: 使用 cron 或 systemd timer

```bash
# cron 每 6 小时运行一次
0 */6 * * * cd /path/to/seed-scanner && uv run python -m src.main /Volumes/xspt --no-mail
```
