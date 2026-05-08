"""
agent/claude.py - Claude on Vertex AI 实现
使用 anthropic[vertex] 库，工具调用能力强
"""
import json
import logging
from google.oauth2 import service_account
from anthropic import AnthropicVertex
from memory.store import history_db, preference_db, memory_db
from tools.registry import registry
import config

log = logging.getLogger(__name__)


class ClaudeAgent:
    def __init__(self, model: str):
        self.model = model

    def _get_client(self) -> AnthropicVertex:
        credentials = service_account.Credentials.from_service_account_file(
            config.CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AnthropicVertex(
            region=config.CLAUDE_REGION,
            project_id=config.GCP_PROJECT_ID,
            credentials=credentials,
        )

    def _build_system(self, user_id: str) -> str:
        from agent.base import get_full_prompt
        parts = [get_full_prompt()]
        pref  = preference_db.get(user_id, "")
        if pref:
            parts.append(f"用户偏好：{pref}")
        mems = [v["value"] for k, v in memory_db.items()
                if k.startswith(user_id + ":")][-5:]
        if mems:
            parts.append("用户长期记忆：\n" + "\n".join(f"- {m}" for m in mems))
        return "\n\n".join(parts)

    def _build_tools(self) -> list:
        """转换为 Claude 工具格式"""
        tools = []
        for decl in registry.get_declarations():
            tools.append({
                "name":         decl["name"],
                "description":  decl["description"],
                "input_schema": decl.get("parameters", {"type": "object", "properties": {}}),
            })
        return tools

    def _load_history(self, user_id: str) -> list:
        """加载对话历史，转为 Claude messages 格式"""
        raw = history_db.get(user_id, [])
        messages = []
        for turn in raw[-(config.MAX_HISTORY_TURNS * 2):]:
            messages.append({
                "role":    turn["role"],
                "content": turn["text"],
            })
        return messages

    def chat(self, user_id: str, user_message: str, context: dict) -> str:
        client   = self._get_client()
        system   = self._build_system(user_id)
        tools    = self._build_tools()
        messages = self._load_history(user_id)
        messages.append({"role": "user", "content": user_message})

        for _ in range(8):  # 最多 8 轮工具调用
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=messages,
            )

            # 收集本轮 assistant 内容
            assistant_content = []
            text_parts        = []
            tool_uses         = []

            for block in response.content:
                assistant_content.append(block)
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # 没有工具调用，结束
            if not tool_uses:
                break

            # 把 assistant 这轮回复加入历史
            messages.append({"role": "assistant", "content": assistant_content})

            # 执行工具并收集结果
            tool_results = []
            for tu in tool_uses:
                log.info(f"工具调用 [{tu.name}]: {json.dumps(dict(tu.input))[:80]}")
                result = registry.execute(tu.name, dict(tu.input), context)
                log.info(f"工具结果 [{tu.name}]: {str(result)[:80]}")
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tu.id,
                    "content":     str(result),
                })

            messages.append({"role": "user", "content": tool_results})

        # 提取最终文本回复
        reply = "".join(
            b.text for b in response.content
            if hasattr(b, "text") and b.text
        ).strip() or "（无回复）"

        # 更新历史
        raw = history_db.get(user_id, [])
        raw.append({"role": "user",      "text": user_message})
        raw.append({"role": "assistant", "text": reply})
        history_db[user_id] = raw[-(config.MAX_HISTORY_TURNS * 2):]

        return reply
