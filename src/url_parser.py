"""URL 解析工具函数（arXiv、CVF、HuggingFace、GitHub）"""
import re
from typing import Optional


ARXIV_PATTERN = re.compile(r'https?://(?:www\.)?arxiv\.org/(?:abs|html|pdf)/\d+\.\d+')
CVF_PATTERN = re.compile(r'https?://openaccess\.thecvf\.com/content/\w+/papers/[^/]+?\.pdf')
HF_PATTERN = re.compile(r'https?://huggingface\.co/papers/(\d+\.\d+)')


def extract_arxiv_id(url: str) -> str:
    """
    从 arXiv URL 提取 ID

    Args:
        url: arXiv URL

    Returns:
        arXiv ID (不含版本号)
    """
    if not url:
        return ""
    # 从 URL 中提取 ID
    arxiv_id = url.split("/")[-1].split("v")[0]
    return arxiv_id


def extract_paper_id(url: str) -> str:
    """
    从 URL 提取论文 ID (arXiv、CVF 或 Hugging Face)

    Args:
        url: 论文 URL

    Returns:
        论文 ID
    """
    if not url:
        return ""

    # arXiv
    if m := ARXIV_PATTERN.search(url):
        return m.group(0).split("/")[-1].split("v")[0]

    # CVF
    if m := CVF_PATTERN.search(url):
        filename = m.group(0).split("/")[-1]
        # 移除 _paper.pdf 后缀
        return filename.replace("_paper.pdf", "")

    # Hugging Face Papers
    if m := HF_PATTERN.search(url):
        return m.group(1).split("v")[0]

    return ""


def parse_paper_url(text: str) -> Optional[str]:
    """
    从文本中提取论文 URL (arXiv、CVF 或 Hugging Face)

    Args:
        text: 待解析的文本

    Returns:
        找到的论文 URL (Hugging Face URL 会转换为 arXiv URL)，未找到则返回 None
    """
    # 优先匹配 arXiv
    if match := ARXIV_PATTERN.search(text):
        return match.group(0)
    # 匹配 CVF
    if match := CVF_PATTERN.search(text):
        return match.group(0)
    # 匹配 Hugging Face Papers，转换为 arXiv URL
    if match := HF_PATTERN.search(text):
        arxiv_id = match.group(1)
        return build_arxiv_url(arxiv_id)
    return None


def build_arxiv_url(arxiv_id: str) -> str:
    """
    构建 arXiv URL

    Args:
        arxiv_id: arXiv ID

    Returns:
        arXiv URL
    """
    return f"https://arxiv.org/abs/{arxiv_id}"


GITHUB_PATTERN = re.compile(
    r'https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[\w.-]+)(?:\.git)?(?:/.*)?'
)


def extract_github_repo_id(url: str) -> str | None:
    """从 GitHub URL 提取 owner_repo 格式的 ID。"""
    if not url:
        return None
    if m := GITHUB_PATTERN.search(url):
        return f"{m.group('owner')}_{m.group('repo')}"
    return None


def parse_github_url(text: str) -> str | None:
    """从文本中提取 GitHub 仓库 URL。"""
    if m := GITHUB_PATTERN.search(text):
        return m.group(0)
    return None
