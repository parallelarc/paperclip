"""
Hugging Face Papers 数据获取
"""
import asyncio
import logging
import re
from datetime import date, timedelta
from typing import List, Dict, Optional

import httpx

from .config import settings

logger = logging.getLogger(__name__)


async def fetch_hf_paper_ids(
    client: httpx.AsyncClient,
    target_date: date
) -> List[str]:
    """
    从 Hugging Face Papers 页面获取论文 ID 列表

    Args:
        client: httpx 异步客户端
        target_date: 目标日期

    Returns:
        论文 ID 列表
    """
    try:
        url = f"{settings.hf_papers_base_url}/{target_date.isoformat()}"
        logger.info(f"获取 {target_date.isoformat()} 的论文列表: {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = await client.get(
            url,
            headers=headers,
            timeout=30,
            follow_redirects=True
        )
        response.raise_for_status()
        html = response.text

        # 从页面中提取论文 ID
        # 方法1: 从缩略图 URL 中提取
        thumbnail_ids = re.findall(r'social-thumbnails/papers/(\d+\.\d+)', html)

        # 方法2: 从链接中提取
        link_ids = re.findall(r'"/papers/(\d+\.\d+)', html)

        # 合并并去重
        all_ids = set(thumbnail_ids + link_ids)

        # 如果没有找到，尝试其他模式
        if not all_ids:
            js_ids = re.findall(r'"id":"(\d+\.\d+)"', html)
            all_ids.update(js_ids)

        logger.info(f"找到 {len(all_ids)} 个论文 ID: {list(all_ids)[:10]}...")
        return sorted(all_ids, reverse=True)

    except Exception as e:
        logger.error(f"获取 Hugging Face 论文 ID 失败: {e}")
        return []


async def fetch_paper_details(
    client: httpx.AsyncClient,
    paper_id: str
) -> Optional[Dict]:
    """
    从 Hugging Face API 获取论文详情

    Args:
        client: httpx 异步客户端
        paper_id: 论文 ID

    Returns:
        论文详情字典，失败返回 None
    """
    try:
        url = settings.hf_paper_api_url.format(paper_id)
        response = await client.get(url, timeout=30)

        if response.status_code == 404:
            logger.warning(f"论文 {paper_id} 不存在或已被删除")
            return None

        response.raise_for_status()
        data = response.json()

        # 检查是否有 arXiv 链接
        paper_url = data.get("paperUrl", "")
        arxiv_id = None

        # 尝试从 paperUrl 中提取 arXiv ID
        if "arxiv.org" in paper_url.lower():
            arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', paper_url)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1)

        # 如果没有 arXiv 链接，使用论文 ID
        if not arxiv_id:
            arxiv_id = paper_id

        return {
            "hfId": paper_id,
            "arxivId": arxiv_id,
            "title": data.get("title", "").strip(),
            "summary": data.get("summary", "")[:500],
            "authors": [a.get("name", "") for a in data.get("authors", [])[:5]],
            "upvotes": data.get("upvotes", 0),
            "paperUrl": paper_url,
            "pdfUrl": data.get("pdfUrl", ""),
            "publishedAt": data.get("publishedAt", ""),
            "aiSummary": data.get("ai_summary", ""),
        }

    except Exception as e:
        logger.error(f"获取论文 {paper_id} 详情失败: {e}")
        return None


async def fetch_hf_papers(
    limit: int = 50,
    skip_ids: set = None,
    days: int = 3
) -> List[Dict]:
    """
    从 Hugging Face Papers 获取最新论文

    Args:
        limit: 获取论文数量上限
        skip_ids: 要跳过的论文 ID 集合
        days: 回溯天数

    Returns:
        论文列表（已去重）
    """
    skip_ids = skip_ids or set()
    today = date.today()
    dates_to_try = [today - timedelta(days=i) for i in range(days)]

    all_papers = []
    seen_ids = set()  # 跟踪本次已添加的论文 ID，防止重复

    async with httpx.AsyncClient() as client:
        for day in dates_to_try:
            if len(all_papers) >= limit:
                break

            logger.info(f"尝试获取 {day.isoformat()} 的论文...")

            paper_ids = await fetch_hf_paper_ids(client, day)

            if not paper_ids:
                continue

            for paper_id in paper_ids:
                if len(all_papers) >= limit:
                    break

                # 跳过已处理的和本次已添加的
                if paper_id in skip_ids or paper_id in seen_ids:
                    continue

                details = await fetch_paper_details(client, paper_id)
                if details and details.get("arxivId"):
                    all_papers.append(details)
                    seen_ids.add(paper_id)  # 标记为已添加

                # 避免请求过快
                await asyncio.sleep(0.5)

    logger.info(f"共获取到 {len(all_papers)} 篇论文")
    return all_papers
