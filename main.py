"""
main.py - 入口文件
只负责初始化和启动，业务逻辑全部在各模块里
"""
import sys
import logging
import lark_oapi as lark

# ─── 日志 ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger(__name__)


def main():
    import config
    from memory.store import cleanup
    from agent.base import build_runtime_context, set_runtime_context, get_current_model
    from tools.registry import registry

    # 1. 清理过期数据
    cleanup()

    # 2. 加载所有内置工具（顺序决定工具声明顺序）
    import tools.builtin.shell
    import tools.builtin.blog
    import tools.builtin.github
    import tools.builtin.memory
    import tools.builtin.system
    import tools.builtin.backup
    log.info(f"内置工具已加载：{registry.list_tools()}")

    # 3. 加载自定义工具（智能体自己创建的）
    registry.load_directory(config.TOOLS_DIR)
    log.info(f"共加载工具 {len(registry.list_tools())} 个")

    # 4. 感知运行环境，注入 system prompt
    ctx = build_runtime_context()
    set_runtime_context(ctx)
    log.info("运行环境感知完成")

    # 5. 启动 Lark WebSocket 长连接
    from lark.handler import do_p2_im_message_receive_v1
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()

    log.info(f"启动 LuckClaw | 模型: {get_current_model()}")
    ws_client = lark.ws.Client(
        config.LARK_APP_ID,
        config.LARK_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
        domain=lark.LARK_DOMAIN,
    )
    ws_client.start()


if __name__ == "__main__":
    main()
