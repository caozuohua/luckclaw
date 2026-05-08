"""
tools/builtin/system.py - 系统状态与自我管理工具
"""
import os
import time
import subprocess
from tools.registry import registry, BaseTool
from memory.store import memory_db, evolution_db, tools_db, history_db
import config


def _run(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


@registry.register
class GetAgentStatusTool(BaseTool):
    name        = "get_agent_status"
    description = "获取 Agent 当前状态，包括模型、记忆、工具数量、系统资源等。"
    parameters  = {"type": "object", "properties": {}}

    def execute(self, args: dict, context: dict) -> str:
        from agent.base import get_current_model
        mem  = _run("free -h | grep Mem | awk '{print $3\"/\"$2}'")
        disk = _run("df -h / | tail -1 | awk '{print $3\"/\"$2}'")
        evo_count = len(evolution_db)
        last_evo  = "从未进化"
        if evo_count > 0:
            last_key  = sorted(evolution_db.keys())[-1]
            last_data = evolution_db[last_key]
            last_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(last_data["timestamp"]))
            last_evo  = f"{last_time}（{last_data['reason']}）"
        return (
            f"🤖 Agent 状态\n"
            f"当前模型：{get_current_model()}\n"
            f"活跃用户：{len(history_db)}\n"
            f"长期记忆：{len(memory_db)} 条\n"
            f"自定义工具：{len(tools_db)} 个\n"
            f"进化次数：{evo_count}\n"
            f"最近进化：{last_evo}\n"
            f"内存：{mem}\n"
            f"磁盘：{disk}"
        )


@registry.register
class SendFileTool(BaseTool):
    name        = "send_file"
    description = "将 VPS 上的文件通过 Lark 发送给用户。支持图片、文本、PDF 等，单文件限 30MB。"
    parameters  = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "VPS 上的文件绝对路径"},
        },
        "required": ["file_path"],
    }

    # 禁止发送的敏感文件
    FORBIDDEN = {
        "/opt/luckclaw/.env",
        "/opt/luckclaw/credentials.json",
        "/home/luckclaw/.github_token",
        "/home/luckclaw/.git-credentials",
    }

    def execute(self, args: dict, context: dict) -> str:
        file_path = args.get("file_path", "")
        if file_path in self.FORBIDDEN:
            return "❌ 安全限制：该文件包含敏感信息，禁止发送"
        if not os.path.exists(file_path):
            return f"❌ 文件不存在：{file_path}"

        # 通过 context 拿到发送函数和用户 ID
        send_fn = context.get("send_file_fn")
        user_id = context.get("user_id", "")
        if not send_fn:
            return "❌ 文件发送功能未初始化"

        send_fn(user_id, file_path)
        size = os.path.getsize(file_path) / 1024
        return f"✅ 文件已发送：{os.path.basename(file_path)}（{size:.1f}KB）"


@registry.register
class ToolCreateTool(BaseTool):
    name        = "tool_create"
    description = "创建新工具：将 shell 或 Python 脚本注册为可调用工具，实现自我扩展。仅限管理员。"
    admin_only  = True
    parameters  = {
        "type": "object",
        "properties": {
            "name":        {"type": "string", "description": "工具名（英文，下划线连接）"},
            "description": {"type": "string", "description": "工具功能描述"},
            "script":      {"type": "string", "description": "脚本内容"},
            "lang":        {"type": "string", "description": "bash 或 python3"},
        },
        "required": ["name", "description", "script", "lang"],
    }

    def execute(self, args: dict, context: dict) -> str:
        name   = args.get("name", "").replace(" ", "_")
        desc   = args.get("description", "")
        script = args.get("script", "")
        lang   = args.get("lang", "bash")

        os.makedirs(config.TOOLS_DIR, exist_ok=True)
        ext         = "sh" if lang == "bash" else "py"
        script_path = f"{config.TOOLS_DIR}/{name}.{ext}"

        with open(script_path, "w") as f:
            header = "#!/bin/bash\n" if lang == "bash" else "#!/usr/bin/env python3\n"
            f.write(header + script)
        os.chmod(script_path, 0o755)

        tools_db[name] = {
            "description": desc,
            "script_path": script_path,
            "lang":        lang,
            "created_at":  time.time(),
        }
        return f"✅ 工具 [{name}] 已创建：{script_path}"


@registry.register
class ToolListTool(BaseTool):
    name        = "tool_list"
    description = "列出所有已注册的内置工具和自定义工具。"
    parameters  = {"type": "object", "properties": {}}

    def execute(self, args: dict, context: dict) -> str:
        from tools.registry import registry as reg
        builtin = reg.list_tools()
        custom  = list(tools_db.keys())
        lines   = [f"📦 内置工具（{len(builtin)} 个）："] + [f"  - {t}" for t in builtin]
        if custom:
            lines += [f"\n🔧 自定义工具（{len(custom)} 个）："] + [
                f"  - {k}: {tools_db[k]['description']}" for k in custom
            ]
        return "\n".join(lines)


@registry.register
class ToolRunTool(BaseTool):
    name        = "tool_run"
    description = "运行一个已注册的自定义工具（通过 tool_create 创建的）。"
    parameters  = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "工具名称"},
            "args": {"type": "string", "description": "传递给工具的参数（JSON 字符串）"},
        },
        "required": ["name"],
    }

    def execute(self, args: dict, context: dict) -> str:
        name      = args.get("name", "")
        tool_args = args.get("args", "{}")
        if name not in tools_db:
            return f"❌ 工具不存在：{name}"
        info        = tools_db[name]
        script_path = info["script_path"]
        lang        = info["lang"]
        cmd = f"bash {script_path} '{tool_args}'" if lang == "bash" \
            else f"/opt/luckclaw/venv/bin/python3 {script_path} '{tool_args}'"
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=60)
            return (r.stdout + r.stderr).strip()[:2000]
        except Exception as e:
            return f"❌ 运行失败: {e}"


@registry.register
class ToolDeleteTool(BaseTool):
    name        = "tool_delete"
    description = "删除一个已注册的自定义工具。仅限管理员。"
    admin_only  = True
    parameters  = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
        },
        "required": ["name"],
    }

    def execute(self, args: dict, context: dict) -> str:
        name = args.get("name", "")
        if name not in tools_db:
            return f"❌ 工具不存在：{name}"
        path = tools_db[name].get("script_path", "")
        if path and os.path.exists(path):
            os.remove(path)
        del tools_db[name]
        return f"✅ 工具 [{name}] 已删除"
