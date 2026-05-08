"""
tools/builtin/backup.py - 备份工具（Turso + 本地）
"""
import os
import time
import subprocess
import shutil
from tools.registry import registry, BaseTool
import config


def _run(cmd: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()[:2000]
    except subprocess.TimeoutExpired:
        return f"❌ 超时（{timeout}s）"
    except Exception as e:
        return f"❌ {e}"


@registry.register
class BackupLocalTool(BaseTool):
    name        = "backup_local"
    description = "备份 agent.db 等关键文件到本地备份目录，保留最近 7 份。"
    parameters  = {
        "type": "object",
        "properties": {
            "files": {
                "type": "string",
                "description": "要备份的文件路径，逗号分隔。默认备份 agent.db"
            }
        }
    }

    BACKUP_DIR = "/opt/luckclaw/backups"

    def execute(self, args: dict, context: dict) -> str:
        files_str = args.get("files", config.DB_PATH)
        files     = [f.strip() for f in files_str.split(",") if f.strip()]

        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        ts      = time.strftime("%Y%m%d_%H%M%S")
        results = []

        for src in files:
            if not os.path.exists(src):
                results.append(f"❌ 不存在：{src}")
                continue
            fname = os.path.basename(src)
            dst   = f"{self.BACKUP_DIR}/{fname}.{ts}.bak"
            try:
                shutil.copy2(src, dst)
                size = os.path.getsize(dst) / 1024
                results.append(f"✅ {fname} → {dst} ({size:.1f}KB)")
            except Exception as e:
                results.append(f"❌ {fname}: {e}")

        # 每个文件只保留最近 7 份
        for src in files:
            fname = os.path.basename(src)
            baks  = sorted([
                f for f in os.listdir(self.BACKUP_DIR)
                if f.startswith(fname) and f.endswith(".bak")
            ])
            for old in baks[:-7]:
                os.remove(f"{self.BACKUP_DIR}/{old}")

        return "\n".join(results)


@registry.register
class BackupTursoTool(BaseTool):
    name        = "backup_turso"
    description = (
        "将 agent.db 备份到 Turso 云数据库。"
        "首次使用需先执行 turso auth login，或在 .env 配置 TURSO_DB_URL 和 TURSO_AUTH_TOKEN。"
    )
    admin_only  = True
    parameters  = {
        "type": "object",
        "properties": {
            "db_name": {
                "type": "string",
                "description": "Turso 数据库名，默认 luckclaw-backup"
            }
        }
    }
    '''
    def execute(self, args: dict, context: dict) -> str:
        db_name   = args.get("db_name", "luckclaw-backup")
        db_url    = os.environ.get("TURSO_DB_URL", "")
        auth_token = os.environ.get("TURSO_AUTH_TOKEN", "")

        if not db_url or not auth_token:
            return (
                "❌ 未配置 Turso 连接信息\n"
                "请在 .env 添加：\n"
                "TURSO_DB_URL=libsql://你的db.turso.io\n"
                "TURSO_AUTH_TOKEN=你的token"
            )

        # 用 turso CLI 推送本地 SQLite 到 Turso
        result = _run(
            f"turso db shell {db_url} "
            f"--auth-token {auth_token} "
            f'".restore {config.DB_PATH}"',
            timeout=120
        )

        if "error" in result.lower():
            # 备选：直接用 HTTP API 上传
            return f"turso CLI 方式失败，尝试备选方案...\n{result}"

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        return f"✅ 已备份到 Turso：{db_name}\n时间：{ts}\n{result}"
    '''
    def execute(self, args: dict, context: dict) -> str:
        db_name   = args.get("db_name", "luckclaw-backup")

        # 确保 WAL 模式
        _run(f"sqlite3 {config.DB_PATH} 'PRAGMA journal_mode = WAL'")

        # 执行导入
        result = _run(
            f"turso db import {config.DB_PATH} {db_name} 2>&1",
            timeout=120
        )

        if "error" in result.lower():
            return f"❌ Turso 备份失败：\n{result}"

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        return f"✅ 已备份到 Turso：{db_name}\n时间：{ts}\n{result}"

@registry.register
class BackupStatusTool(BaseTool):
    name        = "backup_status"
    description = "查看本地备份文件列表和状态。"
    parameters  = {"type": "object", "properties": {}}

    def execute(self, args: dict, context: dict) -> str:
        backup_dir = "/opt/luckclaw/backups"
        if not os.path.exists(backup_dir):
            return "📦 暂无备份（目录不存在）"
        files = sorted(os.listdir(backup_dir), reverse=True)
        if not files:
            return "📦 暂无备份文件"
        lines = []
        total = 0
        for f in files[:20]:
            fp    = os.path.join(backup_dir, f)
            size  = os.path.getsize(fp)
            total += size
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(fp)))
            lines.append(f"- {f} ({size/1024:.1f}KB, {mtime})")
        return (
            f"📦 备份目录：{backup_dir}\n"
            f"共 {len(files)} 个文件，总大小 {total/1024:.1f}KB\n\n"
            + "\n".join(lines)
        )
