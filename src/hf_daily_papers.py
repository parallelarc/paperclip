"""
Hugging Face Daily Papers 定时分析脚本

功能：
- 每天（或手动）从 Hugging Face Papers 获取最新论文
- 并发调用 paper-reader skill 分析
- 发送到飞书 webhook

使用方法：
    # 手动运行一次
    python -m src.hf_daily_papers

    # 并发处理（同时分析 10 篇）
    python -m src.hf_daily_papers --concurrent 10

    # 启动定时任务（每天早上 9 点运行）
    python -m src.hf_daily_papers --schedule
"""
import argparse
import asyncio
import logging
import time
from typing import List, Optional

import httpx
import schedule

from .config import settings
from .webhook import send_webhook
from .state import StateManager
from .arxiv import build_arxiv_url
from .analyzer_sdk import analyze_from_url as analyze
from .huggingface import fetch_hf_papers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def send_summary_webhook(title: str, papers: List[dict]):
    """发送汇总消息到飞书"""
    paper_titles = [
        p.get("title", p.get("arxivId", ""))[:80] + "..."
        if len(p.get("title", p.get("arxivId", ""))) > 80
        else p.get("title", p.get("arxivId", ""))
        for p in papers
    ]

    content_lines = [
        f"# {title}",
        f"",
        f"📊 **共 {len(papers)} 篇论文**",
        f"",
        f"**论文列表：**",
    ]

    for i, paper_title in enumerate(paper_titles, 1):
        content_lines.append(f"{i}. {paper_title}")

    await send_webhook("\n".join(content_lines), icon="🤗", template="blue")


async def process_single_paper(paper: dict, index: int, total: int, sem: asyncio.Semaphore, state: StateManager) -> bool:
    """
    处理单篇论文（用于并发执行）

    Args:
        paper: 论文信息字典
        index: 论文序号
        total: 总论文数
        sem: 并发信号量
        state: 状态管理器

    Returns:
        是否成功处理
    """
    async with sem:
        arxiv_id = paper["arxivId"]
        title = paper.get("title", arxiv_id)
        logger.info(f"[{index}/{total}] 处理: {title[:60]}...")

        arxiv_url = build_arxiv_url(arxiv_id)

        # 执行分析
        result = await asyncio.to_thread(analyze, arxiv_url)

        if result["returncode"] == 0:
            await send_webhook(result["stdout"])
            state.mark_processed(paper["hfId"])
            logger.info(f"  ✓ 成功: {arxiv_id}")
            return True
        else:
            logger.warning(f"  ✗ 失败: {result.get('error', 'Unknown error')}")
            return False


async def process_papers(limit: int = None, skip_processed: bool = True, concurrent: int = 2):
    """
    处理 Hugging Face Daily Papers（支持并发）

    Args:
        limit: 处理论文数量上限
        skip_processed: 是否跳过已处理的论文
        concurrent: 最大并发数
    """
    logger.info("=" * 60)
    logger.info("开始处理 Hugging Face Daily Papers")
    logger.info(f"并发数: {concurrent}")
    logger.info("=" * 60)

    state = StateManager("hf_papers")

    # 获取要跳过的 ID
    skip_ids = state.get_processed() if skip_processed else set()

    # 获取论文列表
    papers = await fetch_hf_papers(limit=limit or 50, skip_ids=skip_ids, days=5)

    if not papers:
        logger.warning("未获取到任何论文")
        return

    # 过滤已处理的论文
    new_papers = [p for p in papers if p["hfId"] not in skip_ids]

    if not new_papers:
        logger.info("没有新论文需要处理")
        return

    logger.info(f"找到 {len(new_papers)} 篇新论文")

    # 发送开始通知
    await send_summary_webhook(
        f"Hugging Face Papers 分析开始 ({len(new_papers)} 篇, 并发数={concurrent})",
        new_papers
    )

    # 创建并发控制信号量
    sem = asyncio.Semaphore(concurrent)

    # 并发处理所有论文
    tasks = [
        process_single_paper(paper, i, len(new_papers), sem, state)
        for i, paper in enumerate(new_papers, 1)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 统计结果
    success_count = sum(1 for r in results if r is True)
    error_count = sum(1 for r in results if r is False)

    logger.info("=" * 60)
    logger.info(f"处理完成: 成功 {success_count}/{len(new_papers)}, 失败 {error_count}")
    logger.info("=" * 60)


def run_scheduled_task(schedule_time: str, concurrent: int = 2):
    """运行定时任务"""
    logger.info(f"定时任务已启动，每天 {schedule_time} 运行，并发数={concurrent}")
    logger.info("按 Ctrl+C 停止")

    async def job():
        try:
            await process_papers(concurrent=concurrent)
        except Exception as e:
            logger.error(f"定时任务执行出错: {e}", exc_info=True)

    def sync_job():
        asyncio.run(job())

    schedule.every().day.at(schedule_time).do(sync_job)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("定时任务已停止")


def main():
    parser = argparse.ArgumentParser(
        description="Hugging Face Daily Papers 分析工具（支持并发）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python -m src.hf_daily_papers --limit 5
  python -m src.hf_daily_papers --concurrent 10 --limit 20
  python -m src.hf_daily_papers --schedule --concurrent 15
        """
    )
    parser.add_argument(
        "--schedule", "-s",
        action="store_true",
        help=f"启动定时任务（每天运行一次，默认时间: {settings.hf_papers_schedule_time}）"
    )
    parser.add_argument(
        "--time", "-t",
        default=settings.hf_papers_schedule_time,
        help="定时任务运行时间，格式: HH:MM"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="处理论文数量上限"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制处理所有论文，忽略已处理记录"
    )
    parser.add_argument(
        "--concurrent", "-c",
        type=int,
        default=2,
        metavar="N",
        help="最大并发数（默认: 2）"
    )

    args = parser.parse_args()

    if args.schedule:
        run_scheduled_task(args.time, args.concurrent)
    else:
        asyncio.run(process_papers(
            limit=args.limit,
            skip_processed=not args.force,
            concurrent=args.concurrent
        ))


if __name__ == "__main__":
    main()
