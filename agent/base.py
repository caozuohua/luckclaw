"""
agent/base.py - LLM 调用抽象层
支持运行时切换模型，新增模型只需添加对应实现类
"""
import logging
import config

log = logging.getLogger(__name__)

# ─── 运行时状态 ───────────────────────────────────────────────────────────────
_current_model  = config.DEFAULT_MODEL
_current_prompt = config.SYSTEM_PROMPT
_runtime_ctx    = ""


def get_current_model() -> str:
    return _current_model

def set_current_model(model: str):
    global _current_model
    _current_model = model

def get_current_prompt() -> str:
    return _current_prompt

def set_current_prompt(prompt: str):
    global _current_prompt
    _current_prompt = prompt

def get_runtime_context() -> str:
    return _runtime_ctx

def set_runtime_context(ctx: str):
    global _runtime_ctx
    _runtime_ctx = ctx


def build_runtime_context() -> str:
    """启动时感知运行环境，注入到 system prompt"""
    import os, subprocess, pwd
    ctx = {}
    ctx["运行用户"] = pwd.getpwuid(os.getuid()).pw_name

    sudo_r = subprocess.run(
        "sudo -l 2>/dev/null | grep NOPASSWD | awk '{print $NF}'",
        shell=True, capture_output=True, text=True
    )
    ctx["sudo权限"] = sudo_r.stdout.strip() or "无"

    tools_check = ["git", "gh", "hugo", "python3", "curl", "jq", "node", "npm"]
    available   = [t for t in tools_check
                   if subprocess.run(f"which {t}", shell=True, capture_output=True).returncode == 0]
    ctx["已安装工具"] = ", ".join(available)

    gh_r = subprocess.run("gh auth status 2>&1 | head -1",
                          shell=True, capture_output=True, text=True)
    ctx["GitHub状态"] = gh_r.stdout.strip() or "未认证"

    posts_dir  = f"{config.BLOG_DIR}/content/posts"
    post_count = len(os.listdir(posts_dir)) if os.path.exists(posts_dir) else 0
    ctx["博客文章数"] = post_count
    ctx["博客目录"]   = config.BLOG_DIR
    ctx["pip路径"]    = "/opt/luckclaw/venv/bin/pip"

    lines = ["=== 运行环境 ==="]
    for k, v in ctx.items():
        lines.append(f"{k}：{v}")
    return "\n".join(lines)


def get_full_prompt() -> str:
    """拼接完整的 system prompt = 用户配置 + 运行时环境感知"""
    parts = [_current_prompt]
    if _runtime_ctx:
        parts.append(_runtime_ctx)
    return "\n\n".join(parts)


def get_agent(model: str = None):
    """根据模型名获取对应的 Agent 实例"""
    model = model or _current_model
    backend = config.MODEL_BACKENDS.get(model)
    if backend == "claude":
        from agent.claude import ClaudeAgent
        return ClaudeAgent(model)
    elif backend == "gemini":
        from agent.gemini import GeminiAgent
        return GeminiAgent(model)
    else:
        log.warning(f"未知模型 {model}，回退到默认 Gemini")
        from agent.gemini import GeminiAgent
        return GeminiAgent(model)
