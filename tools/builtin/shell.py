"""
tools/builtin/shell.py - Shell 命令执行工具
"""
import subprocess
from tools.registry import registry, BaseTool


@registry.register
class ShellTool(BaseTool):
    name        = "run_shell"
    description = (
        "在 VPS 上执行 shell 命令。可用于查看系统状态、安装软件、管理文件、"
        "运行脚本等。安装软件时直接用 sudo apt-get install -y。仅限管理员。"
    )
    admin_only  = True
    parameters  = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "cwd":     {"type": "string",  "description": "工作目录（可选）"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 30"},
        },
        "required": ["command"],
    }

    # 需要自动加 sudo 的命令前缀
    SUDO_PREFIXES = (
        "apt", "apt-get", "snap install",
        "systemctl restart", "systemctl stop", "systemctl start",
        "nginx", "dd of=",
    )

    def execute(self, args: dict, context: dict) -> str:
        import logging
        log = logging.getLogger(__name__)

        cmd     = args.get("command", "").strip()
        cwd     = args.get("cwd") or None
        timeout = args.get("timeout", 30)

        # 自动补 sudo
        for prefix in self.SUDO_PREFIXES:
            if cmd.startswith(prefix) and not cmd.startswith("sudo"):
                cmd = "sudo " + cmd
                break

        log.info(f"执行命令: {cmd}")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=timeout, cwd=cwd
            )
            output = (result.stdout + result.stderr).strip()
            output = output[:3000]

            # 权限不足时给出提示
            if result.returncode != 0 and "permission denied" in output.lower():
                output += "\n\n💡 提示：尝试在命令前加 sudo 重试"

            return f"退出码: {result.returncode}\n{output}" if output else f"退出码: {result.returncode}"
        except subprocess.TimeoutExpired:
            return f"❌ 命令超时（{timeout}s）"
        except Exception as e:
            return f"❌ 执行失败: {e}"
