#!/usr/bin/env python3
"""arXiv TeX source downloader."""

import io
import shutil
import tarfile
import time
from pathlib import Path
from typing import Optional, Tuple

import httpx


class TeXFetcher:
    """Download and extract TeX sources from arXiv."""

    def __init__(self, arxiv_id: str, output_dir: Path):
        self.arxiv_id = arxiv_id
        self.output_dir = output_dir
        self.tex_source_dir = self.output_dir / "tex_source"

    def fetch(self) -> Tuple[bool, Optional[Path]]:
        """Main flow: download -> extract -> identify main tex."""
        tar_gz_bytes = self._download_tar_gz()
        if not tar_gz_bytes:
            return False, None

        if self.tex_source_dir.exists():
            shutil.rmtree(self.tex_source_dir)
        self.tex_source_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._extract_tar_gz(tar_gz_bytes, self.tex_source_dir)
        except Exception as e:
            print(f"  ❌ TeX 解压失败: {e}")
            return False, None

        main_tex = self._identify_main_tex(self.tex_source_dir)
        if not main_tex:
            print("  ❌ 未识别到主 .tex 文件")
            return False, None

        main_tex_path = self.tex_source_dir / main_tex
        print(f"  ✅ 识别主文件: {main_tex}")
        return True, main_tex_path

    def _download_tar_gz(self) -> Optional[bytes]:
        """Download source package bytes from arXiv e-print endpoint."""
        url = f"https://arxiv.org/e-print/{self.arxiv_id}"
        max_retries = 3

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=60) as client:
                    response = client.get(url, follow_redirects=True)
                    response.raise_for_status()
                    data = response.content
                if not data:
                    raise ValueError("空响应")
                print(f"  ✅ 已下载 TeX 源码: {len(data)} bytes")
                return data
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"  下载 TeX 失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}秒后重试...")
                    time.sleep(wait)
                else:
                    print(f"  ❌ 下载 TeX 失败: {e}")
                    return None
        return None

    def _extract_tar_gz(self, tar_gz_bytes: bytes, extract_dir: Path) -> None:
        """Extract arXiv source package into extract_dir."""
        bio = io.BytesIO(tar_gz_bytes)

        # Most arXiv sources are tarballs. Some can be plain tex content.
        try:
            bio.seek(0)
            with tarfile.open(fileobj=bio, mode="r:*") as tar:
                tar.extractall(path=extract_dir)
            return
        except tarfile.ReadError:
            pass

        # Fallback: treat as a single TeX file.
        content = tar_gz_bytes.decode("utf-8", errors="ignore")
        tex_path = extract_dir / "main.tex"
        tex_path.write_text(content, encoding="utf-8")

    def _identify_main_tex(self, extract_dir: Path) -> Optional[str]:
        """Identify main tex with heuristic priority."""
        tex_files = [p for p in extract_dir.rglob("*.tex") if p.is_file()]
        if not tex_files:
            return None

        priorities = ("main.tex", "ms.tex", "paper.tex")
        by_name = {p.name.lower(): p for p in tex_files}
        for name in priorities:
            if name in by_name:
                return str(by_name[name].relative_to(extract_dir))

        # Heuristic: prefer tex files containing \begin{document}
        candidates = []
        for p in tex_files:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            score = 0
            if "\\begin{document}" in text:
                score += 2
            if "\\documentclass" in text:
                score += 1
            candidates.append((score, p.stat().st_size, p))

        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return str(candidates[0][2].relative_to(extract_dir))

        largest = max(tex_files, key=lambda p: p.stat().st_size)
        return str(largest.relative_to(extract_dir))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download arXiv TeX source")
    parser.add_argument("arxiv_id", help="arXiv ID, e.g. 2601.08689")
    parser.add_argument("-o", "--output", default="/tmp/test_tex_fetcher", help="output dir")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = TeXFetcher(args.arxiv_id, out_dir)
    ok, main_tex = fetcher.fetch()
    if ok and main_tex:
        print(f"✅ 成功: {main_tex}")
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
