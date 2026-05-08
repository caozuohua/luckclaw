"""
tools/builtin/github.py - GitHub 操作工具
"""
import json
import base64
import subprocess
from tools.registry import registry, BaseTool
import config


def _gh_api(method: str, endpoint: str, data: dict = None) -> dict:
    """调用 GitHub API，返回解析后的 JSON"""
    if not config.GITHUB_TOKEN:
        return {"error": "GITHUB_TOKEN 未配置"}
    cmd = (
        f'curl -s -X {method} '
        f'-H "Authorization: token {config.GITHUB_TOKEN}" '
        f'-H "Content-Type: application/json" '
    )
    if data:
        cmd += f"-d '{json.dumps(data)}' "
    cmd += f'"https://api.github.com{endpoint}"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


@registry.register
class GithubRepoListTool(BaseTool):
    name        = "github_repo_list"
    description = "列出 GitHub 账号下的仓库。"
    parameters  = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "description": "all/public/private，默认 all"},
        },
    }

    def execute(self, args: dict, context: dict) -> str:
        if not config.GITHUB_TOKEN:
            return "❌ 未配置 GITHUB_TOKEN"
        rtype = args.get("type", "all")
        data  = _gh_api("GET", f"/user/repos?type={rtype}&per_page=30")
        if isinstance(data, list):
            lines = [
                f"- {r['name']} ({'私有' if r['private'] else '公开'}) {r.get('description','')}"
                for r in data
            ]
            return f"📦 共 {len(data)} 个仓库：\n" + "\n".join(lines)
        return f"❌ 请求失败：{data}"


@registry.register
class GithubFileWriteTool(BaseTool):
    name        = "github_file_write"
    description = "在 GitHub 仓库中创建或更新文件。"
    parameters  = {
        "type": "object",
        "properties": {
            "repo":    {"type": "string", "description": "仓库名"},
            "path":    {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
            "message": {"type": "string", "description": "commit 消息"},
        },
        "required": ["repo", "path", "content", "message"],
    }

    def execute(self, args: dict, context: dict) -> str:
        if not config.GITHUB_TOKEN or not config.GITHUB_USER:
            return "❌ 未配置 GITHUB_TOKEN 或 GITHUB_USER"
        repo    = args.get("repo", "")
        path    = args.get("path", "")
        content = args.get("content", "")
        message = args.get("message", "Update via luckclaw")

        b64 = base64.b64encode(content.encode()).decode()

        # 获取已有文件的 SHA
        existing = _gh_api("GET", f"/repos/{config.GITHUB_USER}/{repo}/contents/{path}")
        payload  = {"message": message, "content": b64}
        if isinstance(existing, dict) and "sha" in existing:
            payload["sha"] = existing["sha"]

        result = _gh_api("PUT", f"/repos/{config.GITHUB_USER}/{repo}/contents/{path}", payload)
        if isinstance(result, dict) and "content" in result:
            action = "更新" if "sha" in payload else "创建"
            return f"✅ 文件已{action}：{path}"
        return f"❌ 操作失败：{result}"


@registry.register
class GithubRepoCreateTool(BaseTool):
    name        = "github_repo_create"
    description = "在 GitHub 上创建新仓库。"
    parameters  = {
        "type": "object",
        "properties": {
            "name":        {"type": "string"},
            "description": {"type": "string"},
            "private":     {"type": "boolean", "description": "是否私有，默认 false"},
        },
        "required": ["name"],
    }

    def execute(self, args: dict, context: dict) -> str:
        if not config.GITHUB_TOKEN:
            return "❌ 未配置 GITHUB_TOKEN"
        result = _gh_api("POST", "/user/repos", {
            "name":        args.get("name", ""),
            "description": args.get("description", ""),
            "private":     args.get("private", False),
            "auto_init":   True,
        })
        if isinstance(result, dict) and "full_name" in result:
            return f"✅ 仓库已创建：https://github.com/{result['full_name']}"
        return f"❌ 创建失败：{result}"
