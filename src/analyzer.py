"""
论文分析核心逻辑
"""
import sys
from pathlib import Path

# 支持直接运行脚本：添加项目根目录到 sys.path
if __name__ == "__main__":
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

import logging
import subprocess

# 支持直接运行脚本时的导入
from .config import settings
from .fetch_paper import fetch_paper

logger = logging.getLogger(__name__)


def get_result_path(paper_id: str) -> Path:
    """
    获取 quick 结果文件路径

    Args:
        paper_id: 论文 ID (arXiv 或 CVF)

    Returns:
        结果文件路径 src/papers/{paper_id}/{paper_id}_quick.md
        （与 fetch_paper.py 的默认 output="papers" 路径保持一致）
    """
    return settings.env_dir / "papers" / paper_id / f"{paper_id}_quick.md"


def _extract_markdown_from_stdout(stdout: str) -> str:
    """
    从 LLM stdout 中提取 markdown 内容

    处理两种情况：
    1. 内容被 ```markdown ... ``` 包裹
    2. 内容以 # 开头（直接是 markdown）
    """
    lines = stdout.strip().split('\n')
    content_lines = []
    in_code_block = False
    found_start = False

    for line in lines:
        # 检查是否在 markdown 代码块中
        if line.strip() == '```markdown' or line.strip() == '```md':
            in_code_block = True
            continue
        if line.strip() == '```' and in_code_block:
            in_code_block = False
            continue

        # 如果在代码块中，直接添加
        if in_code_block:
            content_lines.append(line)
            continue

        # 检查是否是 markdown 标题（开始标记）
        if not found_start and line.startswith('#'):
            found_start = True

        # 找到开始后收集所有内容
        if found_start:
            content_lines.append(line)

    # 如果没有找到 markdown 标题，返回原始内容
    if not content_lines:
        return stdout.strip()

    return '\n'.join(content_lines).strip()


def _run_fetch_script(url: str) -> str:
    """
    执行 fetch_paper，返回 paper_id

    Args:
        url: 论文 URL

    Returns:
        paper_id
    """
    logger.info(f"执行 fetch_paper: {url}")

    paper_id = fetch_paper(
        input_url=url,
        output=str(settings.env_dir / "papers"),
        device=settings.mineru_gpu_device,
        backend=settings.mineru_backend,
    )

    logger.info(f"fetch_paper 成功，paper_id={paper_id}")
    return paper_id


def analyze(arxiv_url: str) -> dict:
    """
    执行论文分析，返回 quick 格式结果

    Args:
        arxiv_url: 论文 URL (arXiv 或 CVF)

    Returns:
        包含 returncode, stdout, stderr 的字典
    """
    # 强制先执行 fetch-paper.py，获取正确的 paper_id
    paper_id = _run_fetch_script(arxiv_url)
    result_file = get_result_path(paper_id)

    # 检查缓存
    if result_file.exists():
        logger.info(f"使用缓存结果: paper_id={paper_id}")
        return {
            "returncode": 0,
            "stdout": result_file.read_text(),
            "cached": True,
            "arxiv_id": paper_id
        }

    logger.info(f"开始分析论文: paper_id={paper_id}")

    # 使用 paper-reader skill
    md_file = f"papers/{paper_id}/{paper_id}.md"
    prompt = (
        f"/paper-reader @{md_file}\n\n"
        f"原始 URL: {arxiv_url}\n\n"
        f"数据已准备好（.md 和 _metadata.json 已存在）。\n"
        f"输出分析结果到 papers/{paper_id}\n\n"
        f"请用中文输出分析内容（保留英文术语/作者名/论文标题）"
    )

    result = subprocess.run(
        ["claude", "--dangerously-skip-permissions", "-p", prompt],
        capture_output=True,
        text=True,
        cwd=str(settings.env_dir),
        timeout=settings.analysis_timeout
    )

    # LLM 执行完成后，检查结果文件
    if result.returncode == 0:
        logger.info(f"LLM 执行成功，检查结果文件: {result_file}")
        if result_file.exists():
            return {
                "returncode": 0,
                "stdout": result_file.read_text(),
                "arxiv_id": paper_id
            }
        # LLM 成功但没生成文件，尝试从 stdout 提取并保存
        if result.stdout and result.stdout.strip():
            logger.info(f"LLM 未写入文件，从 stdout 提取内容并保存到 {result_file}")
            content = _extract_markdown_from_stdout(result.stdout)
            result_file.write_text(content, encoding='utf-8')
            return {
                "returncode": 0,
                "stdout": content,
                "arxiv_id": paper_id
            }
        # LLM 成功但没有输出任何内容
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"LLM 执行成功但未生成结果文件且无 stdout 内容",
            "arxiv_id": paper_id
        }

    # LLM 执行失败
    logger.error(
        f"LLM 执行失败: paper_id={paper_id}, returncode={result.returncode}, "
        f"stderr={result.stderr[:200] if result.stderr else ''}"
    )
    return {
        "returncode": result.returncode,
        "stdout": "",
        "stderr": result.stderr or "LLM execution failed",
        "arxiv_id": paper_id
    }


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description="分析单篇论文")
    parser.add_argument("url", help="论文 URL (arXiv 或 CVF)")

    args = parser.parse_args()

    result = analyze(args.url)

    if result["returncode"] == 0:
        print(result["stdout"])
        sys.exit(0)
    else:
        print(f"分析失败: {result.get('stderr', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)
