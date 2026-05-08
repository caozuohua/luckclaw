#!/bin/bash
# deploy.sh - 一键部署/更新脚本
set -e

INSTALL_DIR="/opt/luckclaw"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

[[ $EUID -ne 0 ]] && echo "请用 sudo 运行" && exit 1

info "停止服务..."
systemctl stop luckclaw || true

info "备份旧 main.py..."
cp $INSTALL_DIR/main.py $INSTALL_DIR/main.py.bak 2>/dev/null || true

info "复制新文件..."
# 复制所有 Python 文件和目录
cp main.py $INSTALL_DIR/
cp config.py $INSTALL_DIR/
cp requirements.txt $INSTALL_DIR/

for dir in lark agent tools memory; do
    mkdir -p $INSTALL_DIR/$dir
    cp -r $dir/* $INSTALL_DIR/$dir/
done

# 创建自定义工具目录
mkdir -p $INSTALL_DIR/tools/custom
mkdir -p /opt/luckclaw/tools/custom

info "安装依赖..."
$INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/requirements.txt -q

info "修复权限..."
chown -R luckclaw:luckclaw $INSTALL_DIR

info "启动服务..."
systemctl start luckclaw
sleep 2
systemctl status luckclaw --no-pager

echo ""
echo -e "${GREEN}部署完成！${NC}"
echo "查看日志：sudo journalctl -u luckclaw -f"
