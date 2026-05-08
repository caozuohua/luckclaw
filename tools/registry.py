"""
tools/registry.py - 工具注册表（插件化核心）
工具通过装饰器自动注册，支持动态加载
"""
import os
import logging
import importlib.util
import pathlib

log = logging.getLogger(__name__)


class BaseTool:
    """所有工具的基类"""
    name:        str  = ""
    description: str  = ""
    admin_only:  bool = False
    parameters:  dict = {"type": "object", "properties": {}}

    def execute(self, args: dict, context: dict) -> str:
        raise NotImplementedError

    @property
    def declaration(self) -> dict:
        return {
            "name":        self.name,
            "description": self.description,
            "parameters":  self.parameters,
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool_class):
        """类装饰器：注册工具"""
        instance = tool_class()
        if not instance.name:
            raise ValueError(f"工具 {tool_class.__name__} 缺少 name 属性")
        self._tools[instance.name] = instance
        log.debug(f"工具已注册: {instance.name}")
        return tool_class

    def load_directory(self, path: str):
        """自动扫描目录，加载所有 .py 工具文件"""
        dirpath = pathlib.Path(path)
        if not dirpath.exists():
            return
        for f in sorted(dirpath.glob("*.py")):
            if f.stem.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"tool_{f.stem}", f)
                mod  = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                log.info(f"已加载工具文件: {f.name}")
            except Exception as e:
                log.error(f"加载工具文件失败 {f.name}: {e}")

    def execute(self, name: str, args: dict, context: dict) -> str:
        if name not in self._tools:
            return f"未知工具: {name}"
        tool = self._tools[name]
        if tool.admin_only and not context.get("is_admin"):
            return f"❌ 权限不足：{name} 仅限管理员使用"
        try:
            return tool.execute(args, context)
        except Exception as e:
            log.error(f"工具 {name} 执行异常: {e}", exc_info=True)
            return f"❌ 工具执行异常: {e}"

    def get_declarations(self) -> list:
        return [t.declaration for t in self._tools.values()]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# 全局注册表单例
registry = ToolRegistry()
