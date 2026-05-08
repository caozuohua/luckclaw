"""
tools/builtin/blog.py - 博客管理工具
"""
import os
import time
import subprocess
from tools.registry import registry, BaseTool
import config


def _run(cmd: str, cwd: str = None, timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout, cwd=cwd)
        return (r.stdout + r.stderr).strip()[:2000]
    except Exception as e:
        return f"❌ {e}"


@registry.register
class BlogWriteTool(BaseTool):
    name        = "blog_write"
    description = "创建或更新博客文章，自动生成 Hugo 格式的 Markdown 文件。"
    parameters  = {
        "type": "object",
        "properties": {
            "title":    {"type": "string", "description": "文章标题"},
            "content":  {"type": "string", "description": "文章正文（Markdown）"},
            "tags":     {"type": "string", "description": "标签，逗号分隔"},
            "draft":    {"type": "boolean", "description": "是否草稿，默认 false"},
            "filename": {"type": "string", "description": "指定文件名（可选，不含路径）"},
        },
        "required": ["title", "content"],
    }

    def execute(self, args: dict, context: dict) -> str:
        title    = args.get("title", "")
        content  = args.get("content", "")
        tags     = args.get("tags", "")
        draft    = args.get("draft", False)
        filename = args.get("filename", "")

        if not filename:
            slug     = title.lower().replace(" ", "-").replace("/", "-")[:50]
            filename = f"{time.strftime('%Y-%m-%d')}-{slug}.md"

        posts_dir = f"{config.BLOG_DIR}/content/posts"
        os.makedirs(posts_dir, exist_ok=True)
        filepath = f"{posts_dir}/{filename}"

        tag_list = [f'"{t.strip()}"' for t in tags.split(",") if t.strip()]
        frontmatter = (
            f'---\n'
            f'title: "{title}"\n'
            f'date: {time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}\n'
            f'draft: {str(draft).lower()}\n'
            f'tags: [{", ".join(tag_list)}]\n'
            f'---\n\n'
        )
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter + content)
            return f"✅ 文章已保存：{filename}\n路径：{filepath}"
        except Exception as e:
            return f"❌ 保存失败: {e}"


@registry.register
class BlogListTool(BaseTool):
    name        = "blog_list"
    description = "列出所有博客文章及其状态。"
    parameters  = {"type": "object", "properties": {}}

    def execute(self, args: dict, context: dict) -> str:
        posts_dir = f"{config.BLOG_DIR}/content/posts"
        if not os.path.exists(posts_dir):
            return "📝 暂无文章（posts 目录不存在）"
        files = sorted(os.listdir(posts_dir), reverse=True)
        if not files:
            return "📝 暂无文章"
        lines = []
        for f in files[:20]:
            fp    = os.path.join(posts_dir, f)
            size  = os.path.getsize(fp)
            mtime = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(fp)))
            lines.append(f"- {f} ({size}B, {mtime})")
        return f"📝 共 {len(files)} 篇文章：\n" + "\n".join(lines)


@registry.register
class BlogPublishTool(BaseTool):
    name        = "blog_publish"
    description = "构建并发布博客（运行 hugo build），可选推送到 GitHub。"
    parameters  = {
        "type": "object",
        "properties": {
            "push_github": {"type": "boolean", "description": "是否推送到 GitHub，默认 false"},
            "commit_msg":  {"type": "string",  "description": "commit 消息（可选）"},
        },
    }

    def execute(self, args: dict, context: dict) -> str:
        push       = args.get("push_github", False)
        commit_msg = args.get("commit_msg", f"Auto publish: {time.strftime('%Y-%m-%d %H:%M')}")

        result = _run("hugo", cwd=config.BLOG_DIR)

        if push and config.GITHUB_TOKEN and config.GITHUB_USER:
            git_cmd = (
                f"cd {config.BLOG_DIR} && "
                f"git add -A && "
                f'git commit -m "{commit_msg}" && '
                f"git push"
            )
            push_result = _run(git_cmd)
            result += f"\n\n📤 GitHub 推送：\n{push_result}"
        elif push:
            result += "\n\n⚠️ GITHUB_TOKEN 或 GITHUB_USER 未配置，跳过推送"

        return result


@registry.register
class BlogDeleteTool(BaseTool):
    name        = "blog_delete"
    description = "删除指定博客文章。"
    parameters  = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "文章文件名"},
        },
        "required": ["filename"],
    }

    def execute(self, args: dict, context: dict) -> str:
        filename = args.get("filename", "")
        filepath = f"{config.BLOG_DIR}/content/posts/{filename}"
        if os.path.exists(filepath):
            os.remove(filepath)
            return f"✅ 已删除：{filename}"
        return f"❌ 文件不存在：{filename}"
