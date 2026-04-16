# Paperclip

**学术论文获取与转换工具** - 将 arXiv/CVF 论文转换为高质量 Markdown。

## 核心特性

- **双路径架构**: TeX 源码优先（高质量）→ PDF 回退（兜底）
- **智能展平**: 自动处理 LaTeX `\input`/`\include` 模块化结构
- **图片优化**: PDF 图表自动转 PNG，统一路径便于 LLM 解析
- **多源支持**: arXiv ID / Hugging Face / CVF 会议论文

## 快速开始


### 获取论文

```bash
# arXiv ID（自动使用 TeX 源码）
python -m src.fetch_paper 2401.08689

# CVF 会议论文
python -m src.fetch_paper https://openaccess.thecvf.com/content/CVPR2025/papers/xxx.pdf

# 自定义输出目录
python -m src.fetch_paper 2401.08689 -o my_papers/
```

### 输出结构

```
papers/{paper_id}/
├── {paper_id}.md              # 最终 Markdown
├── {paper_id}_metadata.json   # 元数据
└── images/                   # 所有图片（PNG 格式）
```

## 架构流程

```
arXiv ID
  ↓
[路径 1] TeX 源码 (优先)
  ├─ 下载 arxiv.org/e-print/{id}
  ├─ 解压 + 识别主文件 (main.tex > ms.tex > heuristics)
  ├─ 展平 LaTeX (递归合并 \input/\include)
  ├─ Pandoc 转换 (--katex --extract-media)
  ├─ 图片处理 (PDF→PNG via ImageMagick)
  └─ Markdown 后处理 (修复图片路径)
  ↓
[路径 2] PDF 回退 (路径 1 失败时)
  ├─ 下载 PDF
  ├─ MinerU OCR 解析
  └─ 输出 Markdown
```

## 核心模块

| 模块 | 功能 |
|------|------|
| `fetch_paper.py` | 主入口，协调整个流程 |
| `tex_fetcher.py` | arXiv TeX 源码下载与主文件识别 |
| `tex_converter.py` | LaTeX 展平 + Pandoc 转换 + 图片处理 |

## 配置选项

```bash
# .env 配置
USE_TEX_PIPELINE=true          # 启用 TeX 路径（默认）
MINERU_GPU_DEVICE=0           # GPU 设备号
MINERU_BACKEND=pipeline        # MinerU 后端
```

### 命令行参数

```bash
python -m src.fetch_paper <input> [options]

--no-tex          # 禁用 TeX 路径，强制 PDF 解析
--force-pdf       # 强制使用 PDF 路径
-b pipeline       # MinerU 后端: pipeline/hybrid-auto-engine/vlm-auto-engine
-d 0             # GPU 设备号
-o papers/        # 输出目录
```

## 依赖

### 系统工具
- **pandoc** - LaTeX → Markdown 转换核心
- **ImageMagick** 7.1+ - PDF 图片转 PNG

### Python 包
- `httpx` - HTTP 客户端
- `pypandoc` - Pandoc Python 绑定（可选，提升性能）
- `mineru[all]` - PDF OCR 解析（回退路径）

## 开发

```python
# Python API
from src.fetch_paper import fetch_paper

paper_id = fetch_paper(
    input_url="2401.08689",
    output="papers/",
    use_tex=True,          # 启用 TeX 路径
    backend="pipeline"      # MinerU 后端
)
```

## License

MIT
