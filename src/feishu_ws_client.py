"""
飞书 WebSocket 长连接客户端

使用 lark-oapi SDK 建立长连接，无需公网 IP 或内网穿透
"""
import httpx
import json
import logging
import mimetypes
import re
import threading
from pathlib import Path
from typing import Optional, Dict

import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody
from lark_oapi.api.im.v1 import PatchMessageRequest, PatchMessageRequestBody
from lark_oapi.api.im.v1 import CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji

from .analyzer_sdk import analyze_from_url as analyze
from .url_parser import parse_paper_url, parse_github_url
from .config import settings
from .deepwiki_client import ask_repo_summary

logger = logging.getLogger(__name__)

# 全局客户端引用
_client: Optional[lark.ws.Client] = None
_thread: Optional[threading.Thread] = None


def _create_client() -> lark.Client:
    """创建 lark 客户端"""
    return lark.Client.builder() \
        .app_id(settings.feishu_app_id) \
        .app_secret(settings.feishu_app_secret) \
        .log_level(lark.LogLevel.INFO) \
        .build()


def _extract_message_id(response) -> Optional[str]:
    """从响应中提取 message_id"""
    if response.data and hasattr(response.data, 'message_id'):
        return response.data.message_id
    return None


def add_reaction(message_id: str, emoji_type: str = "OK") -> None:
    """
    在消息上添加 emoji reaction

    Args:
        message_id: 要 reaction 的消息 ID
        emoji_type: 表情类型，如 "OK" (👍), "SMILE" (😊)
    """
    try:
        client = _create_client()
        request = CreateMessageReactionRequest.builder() \
            .message_id(message_id) \
            .request_body(CreateMessageReactionRequestBody.builder()
                .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                .build()) \
            .build()
        response = client.im.v1.message_reaction.create(request)
        if not response.success():
            logger.warning(f"添加 reaction 失败: message_id={message_id}, code={response.code}, msg={response.msg}")
        else:
            logger.info(f"成功添加 reaction: message_id={message_id}, emoji={emoji_type}")
    except Exception as e:
        logger.warning(f"添加 reaction 异常: message_id={message_id}, error={e}")


def _create_error_card(error_message: str) -> dict:
    """创建错误卡片"""
    return {
        "schema": "2.0",
        "config": {"update_multi": True},
        "body": {
            "elements": [
                {
                    "tag": "markdown",
                    "content": error_message
                }
            ]
        }
    }


def reply_message(message_id: str, content: str) -> Optional[str]:
    """
    回复普通文本消息到话题

    Args:
        message_id: 要回复的消息 ID
        content: 文本内容

    Returns:
        新消息的 message_id，失败返回 None
    """
    client = _create_client()

    request = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(json.dumps({"text": content}))
            .build()) \
        .build()

    response = client.im.v1.message.reply(request)

    if not response.success():
        logger.error(
            f"回复消息失败: message_id={message_id}, "
            f"code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
        )
        return None

    logger.info(f"成功回复消息: message_id={message_id}")
    return _extract_message_id(response)


def reply_card_message(message_id: str, content: str) -> Optional[str]:
    """
    回复卡片消息到话题

    Args:
        message_id: 要回复的消息 ID
        content: markdown 内容

    Returns:
        新消息的 message_id，失败返回 None
    """
    client = _create_client()

    card = {
        "schema": "2.0",
        "config": {"update_multi": True},
        "body": {
            "elements": [
                {
                    "tag": "markdown",
                    "content": content
                }
            ]
        }
    }

    request = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(ReplyMessageRequestBody.builder()
            .msg_type("interactive")
            .content(json.dumps(card))
            .build()) \
        .build()

    response = client.im.v1.message.reply(request)

    if not response.success():
        logger.error(
            f"回复卡片失败: message_id={message_id}, "
            f"code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
        )
        return None

    logger.info(f"成功回复卡片: message_id={message_id}")
    return _extract_message_id(response)


def update_message(message_id: str, template_id: str) -> bool:
    """
    更新消息为模板卡片

    Args:
        message_id: 要更新的消息 ID
        template_id: 模板 ID

    Returns:
        是否成功
    """
    client = _create_client()

    card_content = {
        "type": "template",
        "data": {
            "template_id": template_id
        }
    }

    request = PatchMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(PatchMessageRequestBody.builder()
            .content(json.dumps(card_content))
            .build()) \
        .build()

    response = client.im.v1.message.patch(request)

    if not response.success():
        logger.error(
            f"更新消息失败: message_id={message_id}, template_id={template_id}, "
            f"code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
        )
        return False

    logger.info(f"成功更新消息为模板卡片: message_id={message_id}, template_id={template_id}")
    return True


def _extract_verdict_template(markdown: str) -> str:
    """从 markdown 中提取评价等级并返回对应的模板颜色

    Args:
        markdown: 论文分析 markdown 内容

    Returns:
        模板颜色 (green/blue/grey)，默认 blue
    """
    lines = markdown.split('\n')
    in_verdict = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('##') and 'verdict' in stripped.lower():
            in_verdict = True
            continue
        if in_verdict:
            line_upper = stripped.upper()
            if 'MUST READ' in line_upper:
                return 'green'
            if 'RECOMMEND' in line_upper:
                return 'blue'
            if 'SKIP' in line_upper:
                return 'grey'
            if stripped.startswith('##'):
                break

    return 'blue'


def _upload_image_to_feishu(image_path: Path, client: lark.Client) -> Optional[str]:
    """
    上传图片到飞书，返回 image_key

    Args:
        image_path: 图片本地路径
        client: lark 客户端

    Returns:
        image_key，失败返回 None
    """
    if not image_path.exists():
        logger.warning(f"图片文件不存在: {image_path}")
        return None

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        # 获取文件类型
        img_type = (mimetypes.guess_type(image_path.name)[0] or "image/jpeg").split("/")[-1]

        # 获取 tenant_access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_response = httpx.post(
            token_url,
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret
            },
            timeout=10,
            trust_env=False
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        tenant_access_token = token_data.get("tenant_access_token")

        if not tenant_access_token:
            logger.error(f"获取 tenant_access_token 失败: {token_data}")
            return None

        # 上传图片
        upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
        headers = {"Authorization": f"Bearer {tenant_access_token}"}
        files = {"image": (image_path.name, image_data, f"image/{img_type}")}
        data = {"image_type": "message"}

        upload_response = httpx.post(upload_url, headers=headers, files=files, data=data, timeout=30, trust_env=False)
        result = upload_response.json()

        if upload_response.status_code != 200 or result.get("code") != 0:
            logger.error(f"图片上传失败: status={upload_response.status_code}, response={result}")
            return None

        image_key = result.get("data", {}).get("image_key")
        logger.info(f"图片上传成功: {image_path.name} -> {image_key}")
        return image_key

    except Exception as e:
        logger.error(f"上传图片异常: {image_path}, error={e}")
        return None


def _process_markdown_images(markdown: str, paper_id: str) -> Dict[str, str]:
    """处理 markdown 中的本地图片，上传到飞书

    Args:
        markdown: 原始 markdown 内容
        paper_id: 论文 ID，用于定位图片目录

    Returns:
        {filename: img_key} 的字典
    """
    images_dir = settings.env_dir / "papers" / paper_id / "images"

    if not images_dir.exists():
        logger.debug(f"图片目录不存在: {images_dir}")
        return {}

    client = _create_client()
    image_pattern = r'!\[([^\]]*)\]\((?:\.\./)?images/([^)]+)\)'
    image_keys: Dict[str, str] = {}

    for match in re.finditer(image_pattern, markdown):
        filename = match.group(2)
        if filename in image_keys:
            continue

        image_path = images_dir / filename
        if image_path.exists():
            logger.info(f"上传图片: {filename}")
            img_key = _upload_image_to_feishu(image_path, client)
            if img_key:
                image_keys[filename] = img_key
            else:
                logger.warning(f"图片上传失败: {filename}")
        else:
            logger.warning(f"图片不存在: {image_path}")

    return image_keys


def create_paper_card(markdown: str, arxiv_url: str = "", icon: str = "📄", paper_id: str = "") -> dict:
    """将论文分析的 markdown 转换为飞书卡片格式

    Args:
        markdown: 论文分析 markdown 内容
        arxiv_url: arXiv 论文 URL（用于添加按钮）
        icon: 卡片图标
        paper_id: 论文 ID，用于定位图片目录

    Returns:
        飞书交互式卡片字典
    """
    from .webhook import _build_elements

    image_keys = _process_markdown_images(markdown, paper_id) if paper_id else {}
    title, elements = _build_elements(markdown, image_keys)
    template = _extract_verdict_template(markdown)

    card = {
        "schema": "2.0",
        "config": {"update_multi": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{icon} {title}"},
            "template": template
        },
        "body": {
            "elements": elements
        }
    }

    if arxiv_url:
        card["body"]["elements"].extend([
            {"tag": "hr"},
            {"tag": "markdown", "content": f"[📄 查看原文 (arXiv)]({arxiv_url})"}
        ])

    return card


def update_with_paper_card(message_id: str, markdown: str, arxiv_url: str = "", paper_id: str = "") -> bool:
    """更新消息为论文分析卡片

    Args:
        message_id: 要更新的消息 ID
        markdown: 论文分析 markdown 内容
        arxiv_url: arXiv 论文 URL（用于添加按钮）
        paper_id: 论文 ID，用于定位图片目录

    Returns:
        是否成功
    """
    client = _create_client()
    card = create_paper_card(markdown, arxiv_url, paper_id=paper_id)

    request = PatchMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(PatchMessageRequestBody.builder()
            .content(json.dumps(card))
            .build()) \
        .build()

    response = client.im.v1.message.patch(request)

    if not response.success():
        logger.error(
            f"更新论文卡片失败: message_id={message_id}, "
            f"code: {response.code}, msg: {response.msg}"
        )
        return False

    logger.info(f"成功更新消息为论文卡片: message_id={message_id}")
    return True


def reply_paper_card(message_id: str, markdown: str, arxiv_url: str = "", paper_id: str = "") -> Optional[str]:
    """回复论文分析卡片

    Args:
        message_id: 要回复的消息 ID
        markdown: 论文分析 markdown 内容
        arxiv_url: arXiv 论文 URL（用于添加按钮）
        paper_id: 论文 ID，用于定位图片目录

    Returns:
        新消息的 message_id，失败返回 None
    """
    client = _create_client()
    card = create_paper_card(markdown, arxiv_url, paper_id=paper_id)

    request = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(ReplyMessageRequestBody.builder()
            .msg_type("interactive")
            .content(json.dumps(card))
            .build()) \
        .build()

    response = client.im.v1.message.reply(request)

    if not response.success():
        logger.error(
            f"回复论文卡片失败: message_id={message_id}, "
            f"code: {response.code}, msg: {response.msg}"
        )
        return None

    logger.info(f"成功回复论文卡片: message_id={message_id}")
    return _extract_message_id(response)


# ============================================================================
# 事件处理函数 - 函数名必须符合 SDK 规范
# ============================================================================

def do_p2_im_chat_access_event_bot_p2p_chat_entered_v1(data: lark.im.v1.P2ImChatAccessEventBotP2pChatEnteredV1) -> None:
    """
    处理用户进入机器人私聊事件

    Args:
        data: SDK 传递的 P2ImChatAccessEventBotP2pChatEnteredV1 事件对象
    """
    logger.info(f"[do_p2_im_chat_access_event_bot_p2p_chat_entered_v1] 用户进入私聊")


def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """
    处理接收到的消息事件

    Args:
        data: SDK 传递的 P2ImMessageReceiveV1 事件对象
    """
    logger.info(f"[do_p2_im_message_receive_v1] 收到消息事件")

    try:
        message = data.event.message
        message_id = message.message_id
        content_str = message.content

        logger.info(f"message_id={message_id}")

        # 解析 content
        try:
            content = json.loads(content_str)
            text = content.get("text", "")
            # 富文本消息（post 类型）：从 content 数组中提取所有文本和链接
            if not text and "content" in content:
                parts = []
                for row in content["content"]:
                    for seg in row:
                        if seg.get("tag") == "text":
                            parts.append(seg.get("text", ""))
                        elif seg.get("tag") == "a":
                            parts.append(seg.get("href", seg.get("text", "")))
                text = " ".join(parts)
        except:
            text = content_str

        # 检查是否 @ 机器人
        mentions = message.mentions if hasattr(message, 'mentions') else []
        if not mentions:
            logger.info("消息未 @ 机器人，忽略")
            return

        # 提取 URL：优先论文 → GitHub 仓库
        arxiv_url = parse_paper_url(text)
        github_url = None
        if not arxiv_url:
            github_url = parse_github_url(text)

        if not arxiv_url and not github_url:
            reply_message(
                message_id,
                "未找到有效的论文或 GitHub 仓库链接。请发送 arXiv 链接或 GitHub 仓库 URL。"
            )
            return

        if arxiv_url:
            logger.info(f"找到 arXiv URL: {arxiv_url}")
        else:
            logger.info(f"找到 GitHub URL: {github_url}")

        # 在原消息上添加 reaction，让用户立即看到响应
        add_reaction(message_id)

        # 在独立线程中处理分析（避免阻塞 WebSocket）
        def process():
            try:
                if arxiv_url:
                    result = analyze(arxiv_url)

                    if result["returncode"] == 0:
                        paper_id = result.get("arxiv_id", "")
                        reply_paper_card(message_id, result["stdout"], arxiv_url, paper_id)
                    else:
                        error_msg = f"❌ 论文分析失败: {result.get('stderr', 'Unknown error')}"
                        reply_card_message(message_id, error_msg)
                else:
                    try:
                        summary = ask_repo_summary(github_url)
                        reply_card_message(message_id, summary)
                    except Exception as e:
                        logger.exception(f"仓库分析异常: {github_url}, error={e}")
                        reply_card_message(message_id, f"❌ 仓库分析失败: {str(e)}")

            except Exception as e:
                logger.exception(f"处理异常: message_id={message_id}, error={e}")
                reply_card_message(message_id, f"❌ 处理过程中发生错误: {str(e)}")

        threading.Thread(target=process, daemon=True).start()

    except Exception as e:
        logger.exception(f"处理消息事件异常: error={e}")


# ============================================================================
# WebSocket 客户端启动
# ============================================================================

def _start_lark_client():
    """内部函数：启动飞书 WebSocket 客户端（阻塞调用）"""
    global _client

    event_handler = lark.EventDispatcherHandler.builder(
        "",  # encrypt_key (WebSocket 模式不需要)
        ""   # verification_token (WebSocket 模式不需要)
    ).register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(do_p2_im_chat_access_event_bot_p2p_chat_entered_v1) \
     .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1).build()

    _client = lark.ws.Client(
        settings.feishu_app_id,
        settings.feishu_app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG
    )

    _client.start()


def start_ws_thread() -> Optional[threading.Thread]:
    """
    在独立线程中启动长连接（避免阻塞主程序）

    Returns:
        WebSocket 线程对象
    """
    global _thread

    if _thread and _thread.is_alive():
        logger.warning("WebSocket 客户端已在运行")
        return _thread

    if not settings.feishu_app_id or not settings.feishu_app_secret:
        logger.warning("FEISHU_APP_ID 或 FEISHU_APP_SECRET 未配置")
        return None

    _thread = threading.Thread(target=_start_lark_client, daemon=True)
    _thread.start()
    logger.info("WebSocket 客户端线程已启动")
    return _thread


def stop_ws_client():
    """停止 WebSocket 客户端"""
    global _client, _thread

    if _client:
        try:
            _client.stop()
            logger.info("WebSocket 客户端已停止")
        except Exception as e:
            logger.error(f"停止 WebSocket 客户端异常: {e}")
        _client = None

    _thread = None
