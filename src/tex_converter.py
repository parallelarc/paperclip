#!/usr/bin/env python3
"""Pandoc-based TeX to Markdown converter."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional


def find_balanced_brace(text: str, start: int) -> int:
    """
    从 text[start] 开始，找到匹配 } 的位置。
    假设 text[start] 是 {。使用括号计数，支持任意深度嵌套。
    返回匹配的 } 的索引，不包含则返回 -1。
    """
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        elif c == '\\':
            # 跳过转义字符，避免 } 被错误计为括号闭合
            i += 2
            continue
        i += 1
    return -1


def preprocess_latex_for_pandoc(tex_content: str) -> str:
    """
    预处理 LaTeX 内容，修复 pandoc 无法解析的非标准构造。

    使用括号计数处理任意深度嵌套的大括号。
    """

    def strip_cmd(command: str, text: str) -> str:
        """去除 \command{...} → \command，支持任意深度嵌套"""
        pos = 0
        while True:
            idx = text.find('\\' + command, pos)
            if idx == -1:
                break
            # 找到 { 开始位置
            brace_start = text.find('{', idx)
            if brace_start == -1:
                break
            brace_end = find_balanced_brace(text, brace_start)
            if brace_end == -1:
                break
            # 替换为 \command（无参数）
            text = text[:idx] + '\\' + command + text[brace_end + 1:]
            pos = idx + len(command) + 1
        return text

    # 去除 \makedirs{...}
    tex_content = strip_cmd('makedirs', tex_content)

    # 去除 \makeno{...}
    tex_content = strip_cmd('makeno', tex_content)

    # 去除所有 \centerline{...} 整行（使用括号计数）
    lines = tex_content.split('\n')
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('\\centerline'):
            continue  # 跳过整行
        result_lines.append(line)
    tex_content = '\n'.join(result_lines)

    return tex_content


def flatten_latex_file(tex_file: Path, output: Optional[Path] = None) -> Path:
    """
    递归合并所有\input和\include文件到单个tex文件

    解决Pandoc无法处理LaTeX模块化结构的问题:
    https://github.com/jgm/pandoc/issues/4680

    Args:
        tex_file: 主tex文件路径
        output: 输出文件路径，默认为{原文件名}_flatten.tex

    Returns:
        合并后的tex文件路径
    """
    if output is None:
        output = tex_file.parent / f"{tex_file.stem}_flatten.tex"

    def resolve_input(match):
        """解析并递归插入input/include文件内容"""
        filename = match.group(1).strip()
        # 处理.tex扩展名
        if not filename.endswith('.tex'):
            filename = f"{filename}.tex"

        included_file = tex_file.parent / filename

        if not included_file.exists():
            print(f"  ⚠️  Input文件不存在，保留命令: \\input{{{filename}}}")
            return match.group(0)  # 保留原命令

        content = included_file.read_text(encoding='utf-8')
        # 移除\end{document}等可能导致重复的标记
        content = re.sub(r'\\end\{document\}', '', content)

        # 递归处理嵌套的input/include
        content = input_pattern.sub(resolve_input, content)

        return f"\n% --- Begin included from {filename} ---\n{content}\n% --- End {filename} ---\n"

    content = tex_file.read_text(encoding='utf-8')

    # 匹配 \input{...} 和 \include{...}
    input_pattern = re.compile(r'\\(?:input|include)\{([^}]+)\}', re.MULTILINE)

    # 检测是否有input命令
    if not input_pattern.search(content):
        print(f"  ℹ️  单一LaTeX文件，无需合并")
        return tex_file

    print(f"  🔧 检测到{{input_pattern.findall(content)|len()}}个\\input/\\include命令，开始合并...")

    merged_content = input_pattern.sub(resolve_input, content)
    output.write_text(merged_content, encoding='utf-8')

    print(f"  ✅ 合并完成: {output.name}")
    return output


def convert_pdf_to_png(pdf_path: Path, dpi: int = 200) -> Optional[Path]:
    """
    使用ImageMagick将PDF转换为PNG

    优势:
    - ImageMagick 7.1.2-13已安装
    - 高质量转换
    - 支持多页PDF
    - 自动检测密度

    参数:
        pdf_path: PDF文件路径
        dpi: 分辨率，默认200（足够清晰，文件适中）

    返回:
        PNG文件路径，失败返回None
    """
    try:
        # 生成PNG路径
        png_path = pdf_path.with_suffix('.png')

        # 使用ImageMagick转换为PNG
        cmd = [
            'convert',
            '-density', str(dpi),     # 设置DPI
            str(pdf_path),            # 输入文件
            str(png_path)             # 输出文件
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 验证文件生成了
        if not png_path.exists():
            print(f"  ⚠️  PNG未生成: {png_path.name}")
            return None

        size_kb = png_path.stat().st_size // 1024
        print(f"  📷 PDF→PNG: {png_path.name} ({size_kb}KB)")
        return png_path

    except subprocess.CalledProcessError as e:
        print(f"  ❌ PDF转换失败: {e.stderr}")
        return None
    except Exception as e:
        print(f"  ❌ 转换异常: {e}")
        return None


def post_process_markdown_images(md_file: Path, output_dir: Path) -> None:
    """
    后处理markdown文件，修复图片引用

    功能:
    1. 替换HTML占位符为标准markdown语法
    2. 修正路径 (Figures/ -> images/)
    3. 替换PDF为PNG引用

    处理前:
    <span class="image placeholder" data-original-image-src="Figures/Price_compare.pdf"></span>

    处理后:
    ![Price_compare](images/Price_compare.png)
    """
    content = md_file.read_text(encoding='utf-8')
    original_content = content

    # 1. 匹配pandoc生成的HTML占位符
    # 格式: <span class="image placeholder"+s+data-original-image-src="([^"]+)"+s*.*?</span>
    placeholder_pattern = re.compile(
        r'<span class="image placeholder"' + r'\s+' +
        r'data-original-image-src="([^"]+)"' +
        r'.*?</span>',
        re.DOTALL
    )

    def replace_placeholder(match):
        """替换单个占位符为markdown图片语法"""
        original_path = match.group(1)  # 例如: Figures/Price_compare.pdf

        # 提取文件名（不含扩展名）
        filename = Path(original_path).stem  # 例如: Price_compare

        # 构造新路径: images/filename.png
        new_path = f"images/{filename}.png"

        # 返回标准markdown语法
        return f"![{filename}]({new_path})"

    # 执行替换
    content = placeholder_pattern.sub(replace_placeholder, content)

    # 2. 处理可能存在的标准markdown引用（备用）
    # 将Figures/路径替换为images/
    content = re.sub(r'!\[([^\]]*)\]\(Figures/([^)]+\.pdf)\)',
                  r'![\1](images/\2.png)', content)

    # 3. 将PDF引用替换为PNG
    content = re.sub(r'\.pdf\)', r'.png)', content)

    # 保存修改后的文件
    if content != original_content:
        md_file.write_text(content, encoding='utf-8')
        print(f"  ✅ 已修复图片引用: {md_file.name}")


class PandocConverter:
    """Convert TeX to Markdown with pypandoc first, CLI fallback."""

    def __init__(self, tex_file: Path, output_dir: Path, bib_files: Optional[List[Path]] = None):
        self.tex_file = tex_file
        self.output_dir = output_dir
        self.bib_files = bib_files or []
        # 展平LaTeX文件以解决\input问题
        self.flattened_tex = None

    def convert(self, output_name: Optional[str] = None) -> bool:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        md_name = output_name or f"{self.tex_file.stem}.md"
        md_output = self.output_dir / md_name

        # 展平 + 预处理（修复非标准 LaTeX 构造）
        source_tex = flatten_latex_file(self.tex_file)
        preprocessed_tex = self._preprocess_tex(source_tex)

        if self._convert_with_pypandoc(md_output, preprocessed_tex):
            # 清理临时 flatten 文件
            if source_tex != self.tex_file and source_tex.exists():
                source_tex.unlink()
            return True

        # CLI回退也使用预处理后的文件
        result = self._convert_with_cli(md_output, preprocessed_tex)
        # 清理临时文件
        if source_tex != self.tex_file and source_tex.exists():
            source_tex.unlink()
        return result

    def _preprocess_tex(self, tex_path: Path) -> Path:
        """读取展平后的 tex，预处理后写回（覆盖原文件供 pandoc 使用）"""
        content = tex_path.read_text(encoding='utf-8')
        content = preprocess_latex_for_pandoc(content)
        tex_path.write_text(content, encoding='utf-8')
        return tex_path

    def _build_extra_args(self) -> List[str]:
        # 创建图片目录
        media_dir = self.output_dir / "images"
        media_dir.mkdir(parents=True, exist_ok=True)

        args = [
            "--standalone",
            "--katex",                        # 使用KaTeX处理数学公式
            "--extract-media=" + str(media_dir),  # 提取图片到images目录
            "--markdown-headings=atx",          # 使用ATX标题格式 (# ## ###)
            "-f",
            "latex",
            "-t",
            "gfm+pipe_tables+pipe_tables",       # GitHub风格markdown + pipe表格
            "--wrap=none",                     # 不自动换行
        ]
        for bib in self.bib_files:
            args.append(f"--bibliography={bib}")
        if self.bib_files:
            args.append("--citeproc")
        return args

    def _convert_with_pypandoc(self, md_output: Path, source_tex: Path) -> bool:
        try:
            import pypandoc
        except Exception:
            return False

        try:
            pypandoc.convert_file(
                str(source_tex),
                to="markdown",
                format="latex",
                extra_args=self._build_extra_args(),
                outputfile=str(md_output),
            )
            print(f"  ✅ pypandoc 转换成功: {md_output.name}")
            return True
        except Exception as e:
            print(f"  pypandoc 转换失败，尝试 CLI 回退: {e}")
            return False

    def _convert_with_cli(self, md_output: Path, source_tex: Path) -> bool:
        cmd = [
            "pandoc",
            str(source_tex),
            "-f",
            "latex",
            "-t",
            "gfm+pipe_tables",
            "-o",
            str(md_output),
            "--standalone",
            "--katex",
            "--wrap=none",
        ]
        for bib in self.bib_files:
            cmd.append(f"--bibliography={bib}")
        if self.bib_files:
            cmd.append("--citeproc")

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  ✅ pandoc CLI 转换成功: {md_output.name}")
            return True
        except FileNotFoundError:
            print("  ❌ pandoc 未安装，无法执行 TeX 转换")
            return False
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            if stderr:
                print(f"  ❌ pandoc CLI 转换失败: {stderr}")
            else:
                print("  ❌ pandoc CLI 转换失败")
            return False


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Convert TeX to Markdown with Pandoc")
    parser.add_argument("tex_file", help="path to main .tex file")
    parser.add_argument("-o", "--output", default="/tmp/test_pandoc_converter", help="output directory")
    parser.add_argument("--name", default=None, help="output markdown filename")
    args = parser.parse_args()

    tex_file = Path(args.tex_file)
    output_dir = Path(args.output)
    bib_files = [p for p in tex_file.parent.rglob("*.bib")]

    converter = PandocConverter(tex_file=tex_file, output_dir=output_dir, bib_files=bib_files)
    if converter.convert(output_name=args.name):
        print(f"✅ 成功: {output_dir}")
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
