"""
飞书 Webhook 发送
"""
import logging
import re
from typing import Optional, Dict

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def _build_elements(md_content: str, image_keys: Dict[str, str] = None) -> tuple:
    """将 markdown 转换为 schema 2.0 元素列表

    Args:
        md_content: markdown 内容
        image_keys: 图片文件名到 img_key 的映射

    Returns:
        (title, elements)
    """
    image_keys = image_keys or {}
    lines = md_content.strip().split('\n')
    elements = []
    title = ""
    content_parts = []
    i = 0

    if lines and lines[0].startswith('#'):
        title = lines[0].lstrip('#').strip().split('—')[0].strip()
        i = 1

    for line in lines[i:]:
        stripped = line.strip()

        # 处理图片引用
        img_match = re.match(r'!\[([^\]]*)\]\((?:\.\./)?images/([^)]+)\)', stripped)
        if img_match and not stripped.startswith('#'):
            if content_parts:
                elements.append({"tag": "markdown", "content": '\n'.join(content_parts).strip()})
                content_parts = []

            filename = img_match.group(2)
            img_key = image_keys.get(filename)
            if img_key:
                elements.append({
                    "tag": "img",
                    "img_key": img_key,
                    "alt": {"tag": "plain_text", "content": img_match.group(1)},
                    "preview": True,
                    "scale_type": "fit_horizontal"
                })
            continue

        # 处理标题
        if stripped.startswith('##'):
            if content_parts:
                elements.append({"tag": "markdown", "content": '\n'.join(content_parts).strip()})
                content_parts = []
            elements.append({"tag": "markdown", "content": f"**{stripped.lstrip('#').strip()}**"})
        elif stripped.startswith('#'):
            if content_parts:
                elements.append({"tag": "markdown", "content": '\n'.join(content_parts).strip()})
                content_parts = []
            elements.append({"tag": "markdown", "content": f"**{stripped.lstrip('#').strip()}**"})
        else:
            content_parts.append(line)

    if content_parts:
        elements.append({"tag": "markdown", "content": '\n'.join(content_parts).strip()})

    return title, elements


def _build_card_payload(title: str, elements: list, icon: str, template: str) -> dict:
    """构建飞书卡片 payload

    Args:
        title: 卡片标题
        elements: 元素列表
        icon: 图标
        template: 模板颜色

    Returns:
        card payload 字典
    """
    return {
        "msg_type": "interactive",
        "card": {
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
    }


async def send_webhook(
    content: str,
    title: Optional[str] = None,
    icon: str = "📄",
    template: str = "blue"
) -> None:
    """发送消息到飞书 Webhook

    Args:
        content: markdown 内容
        title: 标题
        icon: 图标
        template: 模板颜色
    """
    if not settings.feishu_webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL 未配置，跳过 webhook 发送")
        return

    extracted_title, elements = _build_elements(content)
    final_title = extracted_title or title or "消息"
    payload = _build_card_payload(final_title, elements, icon, template)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.feishu_webhook_url, json=payload, timeout=30)
            if response.status_code >= 400:
                logger.error(f"Webhook 返回错误: status={response.status_code}, body={response.text[:200]}")
            else:
                logger.info(f"Webhook 发送成功: title={final_title}")
    except Exception as e:
        logger.error(f"Webhook 发送失败: {e}")


async def send_card(
    title: str,
    sections: list,
    icon: str = "📄",
    template: str = "blue"
) -> None:
    """发送结构化卡片到飞书

    Args:
        title: 标题
        sections: 章节列表
        icon: 图标
        template: 模板颜色
    """
    if not settings.feishu_webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL 未配置，跳过 webhook 发送")
        return

    elements = []
    for section in sections:
        if isinstance(section, str):
            _, section_elements = _build_elements(section)
            elements.extend(section_elements)
        elif isinstance(section, dict):
            elements.append(section)

    payload = _build_card_payload(title, elements, icon, template)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.feishu_webhook_url, json=payload, timeout=30)
            if response.status_code >= 400:
                logger.error(f"Webhook 返回错误: status={response.status_code}, body={response.text[:200]}")
            else:
                logger.info(f"卡片发送成功: title={title}")
    except Exception as e:
        logger.error(f"卡片发送失败: {e}")
