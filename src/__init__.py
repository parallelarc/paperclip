"""
飞书论文分析机器人
"""
from .config import settings
from .webhook import send_webhook, send_card
from .url_parser import extract_arxiv_id, extract_paper_id, parse_paper_url, parse_github_url, extract_github_repo_id
from .analyzer_sdk import analyze_from_url as analyze
from .deepwiki_client import ask_repo_summary
from .state import StateManager

__all__ = [
    "settings",
    "send_webhook",
    "send_card",
    "extract_arxiv_id",
    "extract_paper_id",
    "parse_paper_url",
    "parse_github_url",
    "extract_github_repo_id",
    "analyze",
    "ask_repo_summary",
    "StateManager",
]
