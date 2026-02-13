#!/usr/bin/env python3
"""
论文获取脚本

使用 MinerU Python API 从 PDF URL 下载并转换为 JSON 和 Markdown 格式。

支持的来源:
    - arXiv: 2407.11730 或 https://arxiv.org/abs/2407.11730
    - HuggingFace: https://huggingface.co/papers/2407.11730 (自动提取 arXiv ID)
    - CVF: https://openaccess.thecvf.com/content/CVPR2025/papers/xxx.pdf

用法:
    python fetch-paper.py 2407.11730
    python fetch-paper.py https://arxiv.org/abs/2407.11730
    python fetch-paper.py https://huggingface.co/papers/2407.11730
    python fetch-paper.py https://openaccess.thecvf.com/content/CVPR2025/papers/xxx.pdf
    python fetch-paper.py <url> --output papers/
    python fetch-paper.py <url> --backend pipeline    # 使用 pipeline 后端 (更快)

输出:
    {paper_id}.md             # Markdown 内容
    {paper_id}_middle.json    # 完整文档结构
    {paper_id}_metadata.json  # 论文元数据
"""
import argparse
import httpx
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Tuple


def detect_source(url_or_id: str) -> Tuple[str, str]:
    """检测论文来源并返回 (source_type, arxiv_id_or_url)

    支持:
    - arXiv ID: 2407.11730
    - arXiv URL: https://arxiv.org/abs/2407.11730
    - HuggingFace: https://huggingface.co/papers/2407.11730 (复用 arXiv 数据)
    - CVF PDF: https://openaccess.thecvf.com/content/CVPR2025/papers/xxx.pdf
    """
    # 纯 arXiv ID
    arxiv_match = re.match(r'^(\d+\.\d+)$', url_or_id.strip())
    if arxiv_match:
        return 'arxiv', url_or_id.strip()

    if not url_or_id.startswith('http'):
        raise ValueError(f"无法识别的输入格式: {url_or_id}")

    # HuggingFace Papers -> 提取 arXiv ID，复用 arXiv 流程
    if 'huggingface.co/papers' in url_or_id:
        match = re.search(r'papers/(\d+\.\d+)', url_or_id)
        if match:
            return 'arxiv', match.group(1)  # 直接返回 arXiv ID

    # arXiv URL
    if 'arxiv.org' in url_or_id:
        match = re.search(r'(\d+\.\d+)', url_or_id)
        if match:
            return 'arxiv', match.group(1)

    # CVF OpenAccess
    if 'openaccess.thecvf.com' in url_or_id:
        return 'cvf', url_or_id

    raise ValueError(f"不支持的论文来源: {url_or_id}")


def parse_arxiv_id(input_str: str) -> str:
    """从输入字符串提取 arXiv ID (保留兼容)"""
    source, normalized = detect_source(input_str)
    if source == 'arxiv':
        return normalized
    raise ValueError(f"不是 arXiv 来源: {input_str}")


def fetch_arxiv_metadata(arxiv_id: str) -> dict:
    """从 arXiv API 获取元数据（带重试）

    Args:
        arxiv_id: arXiv 论文 ID

    Returns:
        元数据字典
    """
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    max_retries = 3

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url, follow_redirects=True)
                response.raise_for_status()
                content = response.text
            break
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  获取元数据失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}秒后重试...")
                time.sleep(wait)
            else:
                raise Exception(f"获取 arXiv 元数据失败 (已重试 {max_retries} 次): {e}")

    entry_match = re.search(r'<entry>(.*?)</entry>', content, re.DOTALL)
    if not entry_match:
        raise ValueError(f"无法找到论文信息: {arxiv_id}")

    entry_content = entry_match.group(1)

    def extract_from_entry(tag: str) -> str:
        m = re.search(f'<{tag}[^>]*>(.*?)</{tag}>', entry_content, re.DOTALL)
        return m.group(1).strip() if m else ""

    authors = re.findall(r'<name>([^<]+)</name>', entry_content)
    summary = re.sub(r'<[^>]+>', '', extract_from_entry('summary'))
    published = extract_from_entry('published')[:10]

    return {
        'source': 'arxiv',
        'id': arxiv_id,
        'title': extract_from_entry('title'),
        'authors': authors,
        'summary': summary,
        'published': published,
        'pdf_url': f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        'abs_url': f"https://arxiv.org/abs/{arxiv_id}",
    }


def fetch_cvf_metadata(pdf_url: str) -> dict:
    """从 CVF PDF URL 提取元数据"""
    # 解析 URL: https://openaccess.thecvf.com/content/CVPR2025/papers/Zhou_Cross-Modal_3D_Representation_CVPR_2025_paper.pdf
    # 格式: {FirstAuthor}_{Title}_{Conference}_{Year}_paper.pdf

    filename = pdf_url.split('/')[-1]  # Zhou_Cross-Modal_3D_Representation_CVPR_2025_paper.pdf

    # 提取会议和年份
    conference_match = re.search(r'_(CVPR|ICCV|ECCV|WACV|NeurIPS)_', filename)
    conference = conference_match.group(1) if conference_match else "Unknown"

    year_match = re.search(r'_(\d{4})_paper\.pdf$', filename)
    year = year_match.group(1) if year_match else "Unknown"

    # 提取首作者 (第一个下划线前的部分)
    first_author_match = re.match(r'^([A-Z][a-z]+)_', filename)
    first_author = first_author_match.group(1) if first_author_match else "Unknown"

    # 提取标题 (移除首作者和结尾的 _Conference_Year_paper.pdf)
    title_part = filename
    if first_author_match:
        title_part = title_part[len(first_author_match.group(1)) + 1:]  # 移除 "Author_"
    title_part = re.sub(r'_[A-Z]+_\d{4}_paper\.pdf$', '', title_part)  # 移除尾缀
    title = title_part.replace('_', ' ')

    # 生成 paper_id: 格式为 cvf_{conference}{year}_{method_or_author}
    # 尝试从标题开头提取方法名
    # 支持格式: SDGOCC, BEVFormer, MaskRCNN, Occ3D, RGB-D, 3D-GNN, YOLOv7 等
    # 不匹配普通大写单词如 Cross, Learning, Semantic
    # 正则解释: 驼峰命名（至少2个大写字母）或 连续大写/数字开头，可含连字符
    method_match = re.match(r'^([A-Z][a-z0-9]*(?:[A-Z][a-z0-9]*)+(?:[-:][A-Za-z0-9]+)*|[A-Z0-9]{2,}[a-z0-9]*(?:[-:][A-Za-z0-9]+)*)', title)
    if method_match:
        method = method_match.group(1).rstrip('-:').strip()
        # 长度限制 2-15，且至少包含2个大写字母（避免匹配 "The", "This" 等）
        if 2 <= len(method) <= 15 and sum(c.isupper() for c in method) >= 2:
            paper_id = f"cvf_{conference}{year}_{method}"
        else:
            paper_id = f"cvf_{conference}{year}_{first_author}"
    else:
        # 如果没有明显的方法名，使用首作者姓氏
        paper_id = f"cvf_{conference}{year}_{first_author}"

    return {
        'source': 'cvf',
        'id': paper_id,
        'title': title,
        'authors': [first_author],
        'summary': '',
        'published': f"{year}-01-01",
        'pdf_url': pdf_url,
        'abs_url': pdf_url.replace('_paper.pdf', ''),
    }


def fetch_paper(
    input_url: str,
    output: str = "papers",
    backend: str = "pipeline",
    device: str = "0",
) -> str:
    """获取论文并转换为 JSON + Markdown

    Args:
        input_url: arXiv ID 或 PDF URL (arXiv/CVF/HuggingFace)
        output: 输出目录
        backend: MinerU 后端
        device: GPU 设备号

    Returns:
        paper_id
    """
    os.environ['CUDA_VISIBLE_DEVICES'] = device

    source, normalized = detect_source(input_url)

    if source == 'arxiv':
        metadata = fetch_arxiv_metadata(normalized)
    elif source == 'cvf':
        metadata = fetch_cvf_metadata(input_url)
    else:
        raise ValueError(f"不支持的来源: {source}")

    paper_id = metadata['id']
    print(f"📄 [{metadata['source'].upper()}] {metadata['title'][:60]}...")
    print(f"   作者: {', '.join(metadata['authors'][:3])}{'...' if len(metadata['authors']) > 3 else ''}")
    print(f"   PDF: {metadata['pdf_url']}")

    output_dir = Path(output) / paper_id
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"{paper_id}.md"

    if md_path.exists():
        print("⏭️  已存在，跳过下载")
        print(f"PAPER_ID:{paper_id}")
        return paper_id

    print("⬇️  正在获取 PDF...")

    # 使用 MinerU 解析
    print(f"  正在解析 PDF (后端: {backend})...")
    from mineru.cli.common import do_parse

    pdf_filename = f"{paper_id}.pdf"
    origin_pdf_path = output_dir / f"{paper_id}.pdf_origin.pdf"

    # 检查是否有缓存的原始 PDF
    if origin_pdf_path.exists():
        print(f"  使用缓存的 PDF: {origin_pdf_path}")
        pdf_bytes = origin_pdf_path.read_bytes()
    else:
        print(f"  正在下载 PDF: {metadata['pdf_url']}")
        with httpx.Client(timeout=60) as client:
            response = client.get(metadata['pdf_url'], follow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content
        print(f"  PDF 已下载 ({len(pdf_bytes)} bytes)")

    do_parse(
        output_dir=str(output_dir),
        pdf_file_names=[pdf_filename],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=["en"],
        backend=backend,
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        f_dump_md=True,
        f_dump_middle_json=True,
    )

    # 整理输出文件
    _reorganize_output(output_dir, pdf_filename, paper_id)

    # 保存元数据
    (output_dir / f"{paper_id}_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )

    print(f"✅ {output_dir}")
    print(f"PAPER_ID:{paper_id}")
    return paper_id


def _reorganize_output(output_dir: Path, pdf_filename: str, paper_id: str) -> None:
    """整理 MinerU 输出文件到根目录

    Args:
        output_dir: 输出目录
        pdf_filename: PDF 文件名
        paper_id: 论文 ID
    """
    mineru_output_dirs = [
        output_dir / pdf_filename / "auto",
        output_dir / pdf_filename / "hybrid_auto",
    ]

    mineru_dir = None
    for d in mineru_output_dirs:
        if d.exists():
            mineru_dir = d
            break

    if not mineru_dir:
        parent = output_dir / Path(pdf_filename).stem
        if parent.exists():
            for item in parent.iterdir():
                if item.is_dir() and (item / "images").exists():
                    mineru_dir = item
                    break

    if not mineru_dir:
        # 清理失败的空目录结构
        pdf_dir = output_dir / pdf_filename
        if pdf_dir.exists():
            shutil.rmtree(pdf_dir)
        return

    print("  整理输出文件...")

    for src_file in mineru_dir.iterdir():
        if src_file.is_file():
            dest_file = output_dir / src_file.name
            if dest_file.exists() and dest_file != src_file:
                dest_file.unlink()
            shutil.move(str(src_file), str(dest_file))
            print(f"    {src_file.name}")

    images_dir = mineru_dir / "images"
    if images_dir.exists():
        dest_images = output_dir / "images"
        if dest_images.exists():
            shutil.rmtree(dest_images)
        shutil.move(str(images_dir), str(dest_images))
        print(f"    images/")

    shutil.rmtree(mineru_dir.parent)

    old_md = output_dir / f"{paper_id}.pdf.md"
    new_md = output_dir / f"{paper_id}.md"
    if old_md.exists():
        old_md.rename(new_md)
        print(f"    {paper_id}.md")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='获取论文并转换为 JSON + Markdown (使用 MinerU)')
    parser.add_argument('input', help='arXiv ID 或 PDF URL (arXiv/CVF/HuggingFace)')
    parser.add_argument('-o', '--output', default='papers', help='输出目录')
    parser.add_argument('-b', '--backend', default='pipeline',
                        choices=['pipeline', 'hybrid-auto-engine', 'hybrid-http-client', 'vlm-auto-engine', 'vlm-http-client'],
                        help='MinerU 后端 (默认: pipeline, 更快更稳定)')
    parser.add_argument('-d', '--device', default='0',
                        help='MinerU 使用的 GPU 设备 (默认: 0，使用第二张 GPU 设为 1)')
    args = parser.parse_args()

    fetch_paper(
        input_url=args.input,
        output=args.output,
        backend=args.backend,
        device=args.device,
    )


if __name__ == '__main__':
    main()
