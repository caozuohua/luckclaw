"""
lark/client.py - Lark 消息收发客户端
支持：消息分片 / 发送文件 / 接收文件下载
"""
import os
import json
import time
import logging
import requests
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
import config

log = logging.getLogger(__name__)

lark_client = lark.Client.builder() \
    .app_id(config.LARK_APP_ID) \
    .app_secret(config.LARK_APP_SECRET) \
    .domain(lark.LARK_DOMAIN) \
    .build()

_token_cache: dict = {"token": None, "expires_at": 0}
RECEIVE_DIR = "/opt/luckclaw/received"


def get_tenant_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    resp = requests.post(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": config.LARK_APP_ID, "app_secret": config.LARK_APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 Token 失败: {data}")
    _token_cache["token"]      = data["tenant_access_token"]
    _token_cache["expires_at"] = now + data.get("expire", 7200) - 60
    return _token_cache["token"]


def _send_single(receive_id: str, msg_type: str, content: str,
                 receive_id_type: str = "open_id"):
    request = CreateMessageRequest.builder() \
        .receive_id_type(receive_id_type) \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type(msg_type)
            .content(content)
            .build()
        ).build()
    resp = lark_client.im.v1.message.create(request)
    if not resp.success():
        log.warning(f"发送消息失败: {resp.code} {resp.msg}")


def send_text(receive_id: str, text: str, receive_id_type: str = "open_id"):
    """发送文本消息，自动分片"""
    MAX = config.LARK_MAX_MSG_LEN
    if len(text) <= MAX:
        chunks = [text]
    else:
        chunks = []
        while text:
            if len(text) <= MAX:
                chunks.append(text)
                break
            cut = text.rfind("\n", 0, MAX)
            if cut == -1:
                cut = MAX
            chunks.append(text[:cut])
            text = text[cut:].lstrip("\n")

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        prefix = f"（{i+1}/{total}）\n" if total > 1 else ""
        _send_single(
            receive_id, "text",
            json.dumps({"text": prefix + chunk}),
            receive_id_type,
        )
        if total > 1:
            time.sleep(0.3)
    log.info(f"消息已发送 → {receive_id[:12]}... ({total} 片)")


def upload_file(file_path: str) -> str:
    """上传文件到 Lark，返回 'IMAGE:key' 或 'FILE:key' 或错误"""
    if not os.path.exists(file_path):
        return f"❌ 文件不存在：{file_path}"
    size = os.path.getsize(file_path)
    if size > 30 * 1024 * 1024:
        return f"❌ 文件超过 30MB（{size/1024/1024:.1f}MB）"

    token = get_tenant_token()
    ext   = os.path.splitext(file_path)[1].lower()
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    with open(file_path, "rb") as f:
        if ext in image_exts:
            resp = requests.post(
                "https://open.larksuite.com/open-apis/im/v1/images",
                headers={"Authorization": f"Bearer {token}"},
                data={"image_type": "message"},
                files={"image": f},
                timeout=60,
            )
            data = resp.json()
            if data.get("code") == 0:
                return f"IMAGE:{data['data']['image_key']}"
            return f"❌ 图片上传失败：{data.get('msg')}"
        else:
            filename = os.path.basename(file_path)
            resp = requests.post(
                "https://open.larksuite.com/open-apis/im/v1/files",
                headers={"Authorization": f"Bearer {token}"},
                data={"file_type": "stream", "file_name": filename},
                files={"file": (filename, f)},
                timeout=60,
            )
            data = resp.json()
            if data.get("code") == 0:
                return f"FILE:{data['data']['file_key']}"
            return f"❌ 文件上传失败：{data.get('msg')}"


def send_file(receive_id: str, file_path: str, receive_id_type: str = "open_id"):
    """发送文件或图片消息"""
    result = upload_file(file_path)
    if result.startswith("IMAGE:"):
        content  = json.dumps({"image_key": result[6:]})
        msg_type = "image"
    elif result.startswith("FILE:"):
        content  = json.dumps({
            "file_key":  result[5:],
            "file_name": os.path.basename(file_path),
        })
        msg_type = "file"
    else:
        send_text(receive_id, result, receive_id_type)
        return
    _send_single(receive_id, msg_type, content, receive_id_type)
    log.info(f"文件已发送：{os.path.basename(file_path)} → {receive_id[:12]}...")


def download_file(file_key: str, filename: str = "") -> str:
    """从 Lark 下载文件到本地，返回保存路径或错误信息"""
    os.makedirs(RECEIVE_DIR, exist_ok=True)
    token     = get_tenant_token()
    filename  = filename or f"received_{int(time.time())}"
    save_path = f"{RECEIVE_DIR}/{filename}"

    resp = requests.get(
        f"https://open.larksuite.com/open-apis/im/v1/files/{file_key}/content",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
        stream=True,
    )
    if resp.status_code != 200:
        return f"❌ 下载失败：HTTP {resp.status_code}"

    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size = os.path.getsize(save_path) / 1024
    log.info(f"文件已下载：{save_path} ({size:.1f}KB)")
    return save_path


def download_image(image_key: str, filename: str = "") -> str:
    """从 Lark 下载图片到本地，返回保存路径"""
    os.makedirs(RECEIVE_DIR, exist_ok=True)
    token     = get_tenant_token()
    filename  = filename or f"img_{int(time.time())}.jpg"
    save_path = f"{RECEIVE_DIR}/{filename}"

    resp = requests.get(
        f"https://open.larksuite.com/open-apis/im/v1/images/{image_key}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
        stream=True,
    )
    if resp.status_code != 200:
        return f"❌ 下载失败：HTTP {resp.status_code}"

    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size = os.path.getsize(save_path) / 1024
    log.info(f"图片已下载：{save_path} ({size:.1f}KB)")
    return save_path
