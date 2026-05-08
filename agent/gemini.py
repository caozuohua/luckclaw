"""
agent/gemini.py - Gemini on Vertex AI 实现
作为 Claude 的备用/降级方案
"""
import logging
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import (
    GenerativeModel, Tool, FunctionDeclaration, Part, Content
)
from memory.store import history_db, preference_db, memory_db
from tools.registry import registry
import config

log = logging.getLogger(__name__)


class GeminiAgent:
    def __init__(self, model: str):
        self.model = model

    def _init_vertex(self):
        credentials = service_account.Credentials.from_service_account_file(
            config.CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        vertexai.init(
            project=config.GCP_PROJECT_ID,
            location=config.GCP_LOCATION,
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

    def _build_tools(self) -> Tool:
        declarations = []
        for decl in registry.get_declarations():
            declarations.append(FunctionDeclaration(
                name=decl["name"],
                description=decl["description"],
                parameters=decl.get("parameters", {"type": "object", "properties": {}}),
            ))
        return Tool(function_declarations=declarations)

    def _load_history(self, user_id: str) -> list:
        raw = history_db.get(user_id, [])
        return [
            Content(role=t["role"], parts=[Part.from_text(t["text"])])
            for t in raw[-(config.MAX_HISTORY_TURNS * 2):]
        ]

    def chat(self, user_id: str, user_message: str, context: dict) -> str:
        self._init_vertex()
        system  = self._build_system(user_id)
        model   = GenerativeModel(
            self.model,
            system_instruction=system,
            tools=[self._build_tools()],
        )
        history = self._load_history(user_id)
        chat    = model.start_chat(history=history, response_validation=False)
        message = user_message

        for _ in range(8):
            response  = chat.send_message(message)
            candidate = response.candidates[0]

            tool_calls = [
                p for p in candidate.content.parts
                if hasattr(p, "function_call")
                and p.function_call is not None
                and p.function_call.name
            ]
            if not tool_calls:
                break

            tool_results = []
            for part in tool_calls:
                fc     = part.function_call
                log.info(f"工具调用 [{fc.name}]")
                result = registry.execute(fc.name, dict(fc.args), context)
                log.info(f"工具结果 [{fc.name}]: {str(result)[:80]}")
                tool_results.append(Part.from_function_response(
                    name=fc.name, response={"result": result}
                ))
            message = tool_results

        reply = "".join(
            p.text for p in candidate.content.parts
            if hasattr(p, "text") and p.text
        ).strip() or "（无回复）"

        raw = history_db.get(user_id, [])
        raw.append({"role": "user",  "text": user_message})
        raw.append({"role": "model", "text": reply})
        history_db[user_id] = raw[-(config.MAX_HISTORY_TURNS * 2):]

        return reply
