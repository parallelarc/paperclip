"""
SDK 直调版论文分析器 — 替代 subprocess claude CLI 方案

对比原 analyzer.py:
- 去掉 subprocess + claude CLI 依赖
- 2 次串行 API 调用对应 Deep → Quick 管道
- 精确异常捕获（RateLimitError / APIConnectionError / ...）
- 内置指数退避重试
- 直接读写文件，不经过 CLI 的 skill/tool-call 循环
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from anthropic import Anthropic, APIStatusError, RateLimitError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 默认值
# ---------------------------------------------------------------------------
_DEFAULT_TIMEOUT = 600          # 秒，与原版一致
_DEFAULT_MAX_RETRIES = 3
_BACKOFF_BASE = 30              # 退避基数（秒）

# ---------------------------------------------------------------------------
# 模板路径（复用现有 skill 模板）
# ---------------------------------------------------------------------------
_SKILL_DIR = Path(__file__).parent.parent / ".claude" / "skills" / "paper-reader"
_TEMPLATE_DEEP = _SKILL_DIR / "references" / "paper-deep.md"
_TEMPLATE_QUICK = _SKILL_DIR / "references" / "paper-quick.md"


def _load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Prompt 构建
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "你是一位严谨的学术论文分析专家。"
    "严格按照给定的输出模板格式分析论文，用中文输出分析内容，"
    "保留英文术语、作者名和论文标题。"
    "不要包裹在 ```markdown ... ``` 中，直接输出 markdown 内容。"
)


def _build_deep_prompt(paper_md: str, metadata: dict, url: str) -> str:
    return (
        f"## 论文原文\n\n{paper_md}\n\n"
        f"## 元数据\n\n```json\n{json.dumps(metadata, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 原始 URL\n{url}\n\n"
        f"## 分析要求\n\n"
        f"请按照以下模板格式，对上述论文进行完整的深度分析。\n\n"
        f"--- 模板开始 ---\n{_load_template(_TEMPLATE_DEEP)}\n--- 模板结束 ---"
    )


def _build_quick_prompt(deep_md: str, metadata: dict) -> str:
    return (
        f"## 深度分析\n\n{deep_md}\n\n"
        f"## 元数据\n\n```json\n{json.dumps(metadata, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 要求\n\n"
        f"从深度分析中提炼速览，严格按照以下模板格式输出。\n\n"
        f"--- 模板开始 ---\n{_load_template(_TEMPLATE_QUICK)}\n--- 模板结束 ---"
    )


# ---------------------------------------------------------------------------
# API 调用 + 重试
# ---------------------------------------------------------------------------
def _call_with_retry(
    client: Anthropic,
    model: str,
    user_message: str,
    max_tokens: int = 16384,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> str:
    """带指数退避的 API 调用，仅对 RateLimitError 重试。"""

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.3,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # 提取文本块
            text_parts = [
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            ]
            return "\n".join(text_parts).strip()

        except RateLimitError as e:
            if attempt < max_retries:
                wait = _BACKOFF_BASE * attempt
                logger.warning(
                    "429 限流，第 %d/%d 次重试，等待 %ds — %s",
                    attempt, max_retries, wait, e,
                )
                time.sleep(wait)
            else:
                raise

        except APIStatusError as e:
            # 非 429 的 API 错误不重试，直接抛出
            raise RuntimeError(f"API 调用失败 (status={e.status_code}): {e}") from e


# ---------------------------------------------------------------------------
# 核心管道
# ---------------------------------------------------------------------------
def analyze(
    paper_id: str,
    papers_dir: str | Path,
    url: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> dict:
    """
    执行 Deep → Quick 两步管道。

    Args:
        paper_id:   论文 ID，如 "2508.16334"
        papers_dir: papers 目录路径
        url:        原始 URL（写入输出）
        model:      模型名，默认读 env ANTHROPIC_MODEL 或 glm-5
        api_key:    API key，默认读 env ANTHROPIC_API_KEY
        base_url:   自定义 endpoint，默认读 env ANTHROPIC_BASE_URL
        max_retries: 429 重试次数

    Returns:
        {"returncode": 0, "stdout": <quick_md_content>, "arxiv_id": paper_id}
        或 {"returncode": 1, "stderr": <error_msg>, "arxiv_id": paper_id}
    """
    from .config import settings

    papers_dir = Path(papers_dir)
    paper_dir = papers_dir / paper_id

    model = model or settings.anthropic_model
    api_key = api_key or settings.anthropic_api_key
    base_url = base_url or settings.anthropic_base_url

    if not api_key:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "缺少 ANTHROPIC_API_KEY 环境变量",
            "arxiv_id": paper_id,
        }

    # ---- 读取输入 ----
    md_path = paper_dir / f"{paper_id}.md"
    meta_path = paper_dir / f"{paper_id}_metadata.json"

    if not md_path.exists():
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": f"论文文件不存在: {md_path}",
            "arxiv_id": paper_id,
        }

    paper_md = md_path.read_text(encoding="utf-8")
    metadata = {}
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    # ---- 初始化客户端 ----
    # z.ai 等 Anthropic 兼容 API 需要 Bearer 模式（auth_token），
    # 而非原生 Anthropic 的 x-api-key 模式（api_key）。
    # 优先使用 auth_token 参数。
    client_kwargs = {"auth_token": api_key, "timeout": _DEFAULT_TIMEOUT}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = Anthropic(**client_kwargs)

    # ---- 检查缓存：quick 已存在则跳过 ----
    deep_path = paper_dir / f"{paper_id}_deep.md"
    quick_path = paper_dir / f"{paper_id}_quick.md"

    if quick_path.exists():
        logger.info("使用缓存结果: paper_id=%s", paper_id)
        return {
            "returncode": 0,
            "stdout": quick_path.read_text(encoding="utf-8"),
            "cached": True,
            "arxiv_id": paper_id,
        }

    # ---- Step 1: Deep Analysis（支持 deep 缓存跳过）----
    deep_md = None
    if deep_path.exists():
        deep_md = deep_path.read_text(encoding="utf-8")
        logger.info("使用 deep 缓存: paper_id=%s", paper_id)

    if deep_md is None:
        try:
            logger.info("Step 1/2: Deep Analysis — paper_id=%s", paper_id)
            deep_md = _call_with_retry(
                client, model,
                _build_deep_prompt(paper_md, metadata, url),
                max_tokens=16384,
                max_retries=max_retries,
            )
            deep_path.write_text(deep_md, encoding="utf-8")
            logger.info("Deep 完成，写入 %s (%d 字符)", deep_path, len(deep_md))
        except Exception as e:
            logger.error("Deep 分析失败: paper_id=%s — %s", paper_id, e)
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": f"Deep 分析失败: {e}",
                "arxiv_id": paper_id,
            }

    # ---- Step 2: Quick Scan ----
    try:
        logger.info("Step 2/2: Quick Scan — paper_id=%s", paper_id)
        quick_md = _call_with_retry(
            client, model,
            _build_quick_prompt(deep_md, metadata),
            max_tokens=4096,
            max_retries=max_retries,
        )
        quick_path.write_text(quick_md, encoding="utf-8")
        logger.info("Quick 完成，写入 %s (%d 字符)", quick_path, len(quick_md))
    except Exception as e:
        logger.error("Quick 失败: paper_id=%s — %s", paper_id, e)
        # Quick 失败，尝试从 deep 提取一段作为 fallback
        quick_md = _extract_quick_fallback(deep_md)
        if quick_md:
            quick_path.write_text(quick_md, encoding="utf-8")
            return {
                "returncode": 0,
                "stdout": quick_md,
                "arxiv_id": paper_id,
            }
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": f"Quick 生成失败且无 fallback: {e}",
            "arxiv_id": paper_id,
        }

    return {
        "returncode": 0,
        "stdout": quick_md,
        "arxiv_id": paper_id,
    }


def _extract_quick_fallback(deep_md: str) -> Optional[str]:
    """从 deep 分析中提取前几段作为简易 quick 替代。"""
    if not deep_md:
        return None
    lines = deep_md.split("\n")
    # 取到第一个二级标题之后的内容（标题 + 摘要部分）
    kept = []
    h2_count = 0
    for line in lines:
        kept.append(line)
        if line.startswith("## "):
            h2_count += 1
            if h2_count >= 3:
                break
    return "\n".join(kept) if len(kept) > 5 else None


# ---------------------------------------------------------------------------
# 兼容旧接口：analyze_from_url(url) → fetch + SDK analyze
# ---------------------------------------------------------------------------
def analyze_from_url(url: str) -> dict:
    """
    从 URL 下载论文并执行 SDK 分析（兼容旧 analyzer.analyze 接口）。

    Args:
        url: 论文 URL (arXiv / CVF / HuggingFace)

    Returns:
        {"returncode": 0, "stdout": <quick_md>, "arxiv_id": paper_id}
        或 {"returncode": 1, "stderr": <error_msg>, "arxiv_id": paper_id}
    """
    from .config import settings
    from .fetch_paper import fetch_paper

    # 1. 下载论文
    try:
        logger.info("fetch_paper: %s", url)
        paper_id = fetch_paper(
            input_url=url,
            output=str(settings.env_dir / "papers"),
            device=settings.mineru_gpu_device,
            backend=settings.mineru_backend,
        )
        logger.info("fetch_paper 成功: paper_id=%s", paper_id)
    except Exception as e:
        logger.error("fetch_paper 失败: %s — %s", url, e)
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": f"论文下载失败: {e}",
            "arxiv_id": "",
        }

    # 2. SDK 分析
    return analyze(
        paper_id=paper_id,
        papers_dir=settings.env_dir / "papers",
        url=url,
    )
