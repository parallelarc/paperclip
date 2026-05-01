"""DeepWiki MCP 客户端 — 通过 ask_question 获取仓库中文摘要"""

import json
import logging
import re
import time

import httpx

from .config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 30

_SUMMARY_QUESTION = (
    "请用中文总结这个开源项目，包含以下内容：\n"
    "1. 项目定位和核心功能（一句话）\n"
    "2. 技术栈\n"
    "3. 核心模块和架构设计\n"
    "4. 适用场景\n"
    "5. 总体评价（值得深入阅读 / 值得浏览 / 可以跳过）"
)


def _parse_sse(text: str) -> dict:
    """从 SSE 响应中提取所有 JSON-RPC 结果，返回最后一个。"""
    results = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            results.append(json.loads(line[6:]))
    if not results:
        raise RuntimeError(f"无效的 SSE 响应: {text[:200]}")
    # ask_question 可能返回多个事件，最后一个通常是完整回答
    if len(results) > 1:
        logger.debug("SSE 收到 %d 个事件，取最后一个", len(results))
    return results[-1]


def _rpc(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    payload = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params:
        payload["params"] = params
    resp = httpx.post(
        settings.deepwiki_mcp_url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        timeout=120,
        trust_env=False,
    )
    resp.raise_for_status()
    data = _parse_sse(resp.text)
    if "error" in data:
        raise RuntimeError(f"MCP 错误: {data['error']}")
    return data


def _call_tool(name: str, arguments: dict, request_id: int = 1) -> dict:
    return _rpc("tools/call", {"name": name, "arguments": arguments}, request_id)


def _extract_text(result: dict) -> str:
    content = result.get("result", {}).get("content", [])
    parts = [item["text"] for item in content if item.get("type") == "text"]
    text = "\n\n".join(parts)
    if not text:
        logger.warning("DeepWiki 返回空内容, result keys: %s, content: %s",
                       list(result.keys()), content[:200] if content else "[]")
    return text


def ask_repo_summary(repo_url: str) -> str:
    """
    通过 DeepWiki ask_question 获取仓库中文摘要。

    Args:
        repo_url: GitHub 仓库 URL

    Returns:
        中文摘要文本

    Raises:
        RuntimeError: 获取失败
        ValueError: 无效的 GitHub URL
    """
    from .url_parser import extract_github_repo_id
    repo_id = extract_github_repo_id(repo_url)
    if not repo_id:
        raise ValueError(f"无效的 GitHub URL: {repo_url}")

    repo_name = repo_id.replace("_", "/", 1)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            _rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "paperclip", "version": "0.1.0"},
            }, request_id=0)

            logger.info("DeepWiki ask_question: %s", repo_name)
            result = _call_tool("ask_question", {
                "repoName": repo_name,
                "question": _SUMMARY_QUESTION,
            }, request_id=1)
            return _extract_text(result)

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt < _MAX_RETRIES:
                wait = _BACKOFF_BASE * attempt
                logger.warning("DeepWiki 请求失败，第 %d/%d 次重试，等待 %ds — %s",
                               attempt, _MAX_RETRIES, wait, e)
                time.sleep(wait)
            else:
                raise RuntimeError(f"DeepWiki 获取失败: {e}") from e
