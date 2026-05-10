"""tools/builtin/scheduler.py - 定时任务系统"""
import time, threading, subprocess, logging
from tools.registry import registry, BaseTool
from memory.store import tools_db

log = logging.getLogger(__name__)
_tasks: dict = {}  # {name: {interval, command, last_run, thread}}


def _run_task(name: str, command: str, interval: int):
    while name in _tasks:
        time.sleep(interval)
        if name not in _tasks:
            break
        try:
            r = subprocess.run(command, shell=True, capture_output=True,
                               text=True, timeout=60)
            log.info(f"定时任务 [{name}]: 退出码 {r.returncode}")
            _tasks[name]["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            log.error(f"定时任务 [{name}] 失败: {e}")


@registry.register
class ScheduleAddTool(BaseTool):
    name        = "schedule_add"
    description = "添加定时任务，让智能体定期主动执行命令（如备份、检查日志）。仅限管理员。"
    admin_only  = True
    parameters  = {
        "type": "object",
        "properties": {
            "name":     {"type": "string", "description": "任务名称"},
            "command":  {"type": "string", "description": "要执行的 shell 命令"},
            "interval": {"type": "integer", "description": "间隔秒数，如 3600=每小时"},
        },
        "required": ["name", "command", "interval"]
    }

    def execute(self, args: dict, context: dict) -> str:
        name, command, interval = args["name"], args["command"], args["interval"]
        if name in _tasks:
            return f"❌ 任务已存在：{name}，请先用 schedule_remove 删除"
        _tasks[name] = {"command": command, "interval": interval, "last_run": "未执行"}
        t = threading.Thread(target=_run_task, args=(name, command, interval), daemon=True)
        t.start()
        _tasks[name]["thread"] = t
        # 持久化到 db
        tools_db[f"schedule:{name}"] = {"command": command, "interval": interval}
        return f"✅ 定时任务已添加：{name}，每 {interval}s 执行一次"


@registry.register
class ScheduleListTool(BaseTool):
    name        = "schedule_list"
    description = "列出所有定时任务及状态。"
    parameters  = {"type": "object", "properties": {}}

    def execute(self, args: dict, context: dict) -> str:
        if not _tasks:
            return "📅 暂无定时任务"
        lines = [f"- [{k}] 每{v['interval']}s | 上次:{v['last_run']} | {v['command'][:40]}"
                 for k, v in _tasks.items() if k != "thread"]
        return "📅 定时任务：\n" + "\n".join(lines)


@registry.register
class ScheduleRemoveTool(BaseTool):
    name        = "schedule_remove"
    description = "删除定时任务。仅限管理员。"
    admin_only  = True
    parameters  = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"]
    }

    def execute(self, args: dict, context: dict) -> str:
        name = args["name"]
        if name not in _tasks:
            return f"❌ 任务不存在：{name}"
        del _tasks[name]
        tools_db.pop(f"schedule:{name}", None)
        return f"✅ 已删除任务：{name}"


def restore_schedules():
    """启动时从 db 恢复持久化的定时任务"""
    for k, v in tools_db.items():
        if k.startswith("schedule:"):
            name = k[9:]
            _tasks[name] = {"command": v["command"], "interval": v["interval"], "last_run": "未执行"}
            t = threading.Thread(target=_run_task, args=(name, v["command"], v["interval"]), daemon=True)
            t.start()
            _tasks[name]["thread"] = t
            log.info(f"恢复定时任务：{name}")
