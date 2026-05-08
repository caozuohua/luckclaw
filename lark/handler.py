"""
lark/handler.py - 事件处理与指令路由
支持接收：文本 / 文件 / 图片
"""
import json
import logging
import threading
import lark_oapi as lark

from lark.client import send_text, send_file as lark_send_file, \
    download_file, download_image
from memory.store import history_db, preference_db, memory_db
from agent.base import get_agent, get_current_model, set_current_model, \
    build_runtime_context, set_runtime_context
from tools.registry import registry
import config

log = logging.getLogger(__name__)

_processed_ids: set = set()


def handle_command(user_id: str, text: str):
    cmd = text.strip().lower()

    if cmd == "/help":
        return (
            "🤖 指令列表：\n"
            "/help              帮助\n"
            "/clear             清除对话历史\n"
            "/status            Agent 状态\n"
            "/model             查看/切换模型\n"
            "/tools             工具列表\n"
            "/memory            长期记忆\n"
            "/files             查看已接收的文件\n"
            "/preference <x>    设置偏好\n"
            "/refresh           重新感知运行环境\n"
            "/backup            立即备份数据库\n"
            "\n💡 支持直接发送文件/图片给机器人"
        )

    if cmd == "/clear":
        if user_id in history_db:
            del history_db[user_id]
        return "✅ 对话历史已清除"

    if cmd == "/status":
        return registry.execute("get_agent_status", {}, _make_context(user_id))

    if cmd == "/tools":
        return registry.execute("tool_list", {}, _make_context(user_id))

    if cmd == "/backup":
        return registry.execute("backup_local", {}, _make_context(user_id))

    if cmd == "/files":
        import os, time
        recv_dir = "/opt/luckclaw/received"
        if not os.path.exists(recv_dir):
            return "📁 暂无接收文件"
        files = sorted(os.listdir(recv_dir), reverse=True)[:20]
        if not files:
            return "📁 暂无接收文件"
        lines = []
        for f in files:
            fp    = os.path.join(recv_dir, f)
            size  = os.path.getsize(fp) / 1024
            mtime = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(fp)))
            lines.append(f"- {f} ({size:.1f}KB, {mtime})")
        return f"📁 已接收文件（{len(files)} 个）：\n" + "\n".join(lines)

    if cmd == "/memory":
        items = [(k, v) for k, v in memory_db.items() if k.startswith(user_id + ":")]
        if not items:
            return "📝 暂无长期记忆"
        return "📝 长期记忆：\n" + "\n".join(
            f"- {k.split(':', 1)[-1]}: {v['value']}" for k, v in items
        )

    if cmd.startswith("/preference "):
        pref = text[len("/preference "):].strip()
        preference_db[user_id] = pref
        return f"✅ 偏好已更新：{pref}"

    if cmd == "/refresh":
        ctx = build_runtime_context()
        set_runtime_context(ctx)
        return f"✅ 运行环境已重新感知\n\n{ctx}"

    if cmd.startswith("/model"):
        return _handle_model_cmd(text)

    return None


def _handle_model_cmd(text: str) -> str:
    parts = text.strip().split()
    if len(parts) == 1:
        models = "\n".join(
            f"  {'✅' if m == get_current_model() else '  '} {m} [{b}]"
            for m, b in config.MODEL_BACKENDS.items()
        )
        return f"🤖 当前模型：{get_current_model()}\n\n可用模型：\n{models}\n\n切换：/model gemini-2.5-flash"
    new_model = parts[1]
    if new_model not in config.MODEL_BACKENDS:
        return f"❌ 不支持：{new_model}\n发送 /model 查看可用列表"
    set_current_model(new_model)
    return f"✅ 模型已切换：{new_model}"


def _make_context(user_id: str) -> dict:
    return {
        "user_id":      user_id,
        "is_admin":     not config.ADMIN_USERS or user_id in config.ADMIN_USERS,
        "send_file_fn": lambda uid, path: lark_send_file(uid, path, "open_id"),
    }


def handle_file_message(user_open_id: str, chat_id: str,
                        chat_type: str, message) -> None:
    msg_type = message.message_type
    target   = user_open_id if chat_type == "p2p" else chat_id
    id_type  = "open_id"    if chat_type == "p2p" else "chat_id"

    try:
        content = json.loads(message.content)
    except Exception:
        return

    if msg_type == "image":
        image_key = content.get("image_key", "")
        if not image_key:
            return
        send_text(target, "📥 正在下载图片...", id_type)
        save_path = download_image(image_key)
        if save_path.startswith("❌"):
            send_text(target, save_path, id_type)
            return
        import os
        user_msg = (
            f"用户发来了一张图片，已保存到 {save_path}"
            f"（{os.path.getsize(save_path)/1024:.1f}KB）。"
            f"请告知用户图片已收到，并询问需要如何处理。"
        )
        reply = get_agent().chat(user_open_id, user_msg, _make_context(user_open_id))
        send_text(target, reply, id_type)

    elif msg_type == "file":
        file_key = content.get("file_key", "")
        filename = content.get("file_name", f"file_{int(__import__('time').time())}")
        if not file_key:
            return
        send_text(target, f"📥 正在下载文件：{filename}...", id_type)
        save_path = download_file(file_key, filename)
        if save_path.startswith("❌"):
            send_text(target, save_path, id_type)
            return
        import os
        user_msg = (
            f"用户发来了文件：{filename}"
            f"（{os.path.getsize(save_path)/1024:.1f}KB），"
            f"已保存到 {save_path}。"
            f"请告知用户文件已收到，并询问需要如何处理。"
        )
        reply = get_agent().chat(user_open_id, user_msg, _make_context(user_open_id))
        send_text(target, reply, id_type)


def process_message(user_open_id: str, chat_id: str,
                    chat_type: str, user_text: str):
    target  = user_open_id if chat_type == "p2p" else chat_id
    id_type = "open_id"    if chat_type == "p2p" else "chat_id"

    reply = handle_command(user_open_id, user_text)
    if reply is None:
        try:
            reply = get_agent().chat(
                user_open_id, user_text, _make_context(user_open_id)
            )
        except Exception as e:
            log.error(f"Agent 调用失败: {e}", exc_info=True)
            reply = "抱歉，处理失败，请稍后重试。"

    send_text(target, reply, id_type)


def do_p2_im_message_receive_v1(data) -> None:
    message = data.event.message
    sender  = data.event.sender

    msg_id = message.message_id
    if msg_id in _processed_ids:
        return
    _processed_ids.add(msg_id)
    if len(_processed_ids) > 1000:
        for mid in list(_processed_ids)[:500]:
            _processed_ids.discard(mid)

    user_open_id = sender.sender_id.open_id
    chat_id      = message.chat_id
    chat_type    = message.chat_type
    if not user_open_id:
        return

    msg_type = message.message_type

    if msg_type in ("file", "image"):
        threading.Thread(
            target=handle_file_message,
            args=(user_open_id, chat_id, chat_type, message),
            daemon=True,
        ).start()
        return

    if msg_type != "text":
        return

    try:
        content   = json.loads(message.content)
        user_text = content.get("text", "").strip()
        if "@_user_" in user_text:
            user_text = " ".join(
                w for w in user_text.split() if not w.startswith("@_user_")
            ).strip()
    except Exception:
        return

    if not user_text:
        return

    log.info(f"收到消息 [{user_open_id[:8]}...]: {user_text}")
    threading.Thread(
        target=process_message,
        args=(user_open_id, chat_id, chat_type, user_text),
        daemon=True,
    ).start()
