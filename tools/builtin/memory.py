"""
tools/builtin/memory.py - 记忆工具
"""
import time
from tools.registry import registry, BaseTool
from memory.store import memory_db, evolution_db
import config


@registry.register
class RememberTool(BaseTool):
    name        = "remember"
    description = "将重要信息存入长期记忆，跨会话保留。"
    parameters  = {
        "type": "object",
        "properties": {
            "key":   {"type": "string", "description": "记忆键名"},
            "value": {"type": "string", "description": "要记住的内容"},
        },
        "required": ["key", "value"],
    }

    def execute(self, args: dict, context: dict) -> str:
        key     = args.get("key", "")
        value   = args.get("value", "")
        user_id = context.get("user_id", "global")
        memory_db[f"{user_id}:{key}"] = {"value": value, "timestamp": time.time()}
        return f"✅ 已记住：{key}"


@registry.register
class RecallTool(BaseTool):
    name        = "recall"
    description = "从长期记忆中检索信息。"
    parameters  = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "要检索的键名（支持模糊匹配）"},
        },
        "required": ["key"],
    }

    def execute(self, args: dict, context: dict) -> str:
        key     = args.get("key", "").lower()
        user_id = context.get("user_id", "global")
        results = [
            f"{k.split(':', 1)[-1]}: {v['value']}"
            for k, v in memory_db.items()
            if user_id in k and key in k.lower()
        ]
        return ("📝 找到：\n" + "\n".join(results)) if results else f"未找到：{key}"


@registry.register
class UpdateSystemPromptTool(BaseTool):
    name        = "update_system_prompt"
    description = "更新自己的系统提示词（自我进化）。每次进化都会记录日志。仅限管理员。"
    admin_only  = True
    parameters  = {
        "type": "object",
        "properties": {
            "new_prompt": {"type": "string", "description": "新的系统提示词"},
            "reason":     {"type": "string", "description": "更新原因"},
        },
        "required": ["new_prompt", "reason"],
    }

    def execute(self, args: dict, context: dict) -> str:
        from agent.base import get_current_prompt, set_current_prompt
        new_prompt = args.get("new_prompt", "")
        reason     = args.get("reason", "")
        old_prompt = get_current_prompt()
        set_current_prompt(new_prompt)

        evolution_db[f"evo_{int(time.time())}"] = {
            "timestamp":    time.time(),
            "reason":       reason,
            "old_prompt":   old_prompt,
            "new_prompt":   new_prompt,
            "triggered_by": context.get("user_id", ""),
        }
        return f"✅ 系统提示词已更新\n原因：{reason}"
