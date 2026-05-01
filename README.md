# Paperclip

**飞书论文分析机器人** — 在飞书中 @机器人 发送论文或 GitHub 仓库链接，自动获取分析并返回结构化解读。

## 核心特性

- **飞书交互**: WebSocket 长连接，@机器人 发链接即可触发分析，结果以卡片形式推送
- **论文分析**: 支持 arXiv / Hugging Face Papers / CVF 会议论文，TeX 源码优先 → PDF 回退，三步分析管道（Deep → Notes → Quick）
- **GitHub 仓库总结**: 发送 GitHub URL，通过 DeepWiki 获取中文项目摘要（零 LLM 调用，零 API 成本）
- **每日论文推送**: 定时从 HuggingFace Daily Papers 抓取新论文，并发分析后推送到飞书群

## 快速开始

### 安装

```bash
cd paperclip
uv sync                # 基础依赖
uv sync --extra full   # 含 MinerU OCR（需要 GPU）
```

系统依赖：**pandoc**（LaTeX 转换）、**ImageMagick** 7.1+（PDF 图片转 PNG）

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入：
# - FEISHU_APP_ID / FEISHU_APP_SECRET  （飞书应用凭证，必需）
# - ANTHROPIC_API_KEY                   （论文分析 API Key，必需）
# - FEISHU_WEBHOOK_URL                  （群推送 Webhook，可选）
```

### 运行

```bash
# 启动飞书机器人（WebSocket 模式，无需公网 IP）
python -m src.run_bot

# 手动获取单篇论文
python -m src.fetch_paper 2401.08689

# 手动运行 HuggingFace 每日论文分析
python -m src.hf_daily_papers --limit 5
python -m src.hf_daily_papers --concurrent 10 --limit 20

# 启动定时任务（每天 09:00 自动分析 HF 热门论文）
python -m src.hf_daily_papers --schedule
```

## 使用方式

### 1. 飞书 @机器人

在群聊中 @机器人 并发送链接：

```
@Paperclip https://arxiv.org/abs/2401.08689        # 论文分析
@Paperclip https://github.com/modelcontextprotocol/servers  # GitHub 仓库总结
```

机器人会添加 👍 reaction 表示已收到，分析完成后以卡片形式回复结果。

### 2. HuggingFace 每日推送

定时任务每天自动从 HuggingFace Papers 获取最新热门论文，并发分析后推送 Quick 摘要到飞书群。已处理的论文会跳过，状态持久化在 `state/` 目录。

### 3. 命令行

```bash
python -m src.fetch_paper <arxiv_id_or_url> [-o papers/] [--no-tex]
```

## 架构流程

```
飞书 @机器人 / HF 定时任务
  ↓
[URL 解析] url_parser.py → 识别论文 URL 或 GitHub URL
  ↓
  ├─ 论文路径 ──────────────────────────────────────────────┐
  │   [论文获取] fetch_paper.py                              │
  │   ├─ [路径 1] TeX 源码 (优先)                            │
  │   │   ├─ tex_fetcher: 下载 + 识别主文件                   │
  │   │   └─ tex_converter: 展平 LaTeX → Pandoc → Markdown   │
  │   └─ [路径 2] PDF 回退                                   │
  │       └─ MinerU OCR 解析                                 │
  │   ↓                                                      │
  │   [论文分析] analyzer_sdk.py (Anthropic API 直调)         │
  │   ├─ Step 1: Deep 深度分析                               │
  │   ├─ Step 2: Notes 笔记提炼                              │
  │   └─ Step 3: Quick 速览摘要                              │
  │                                                          │
  └─ GitHub 路径 ────────────────────────────────────────────┘
      [仓库总结] deepwiki_client.py (DeepWiki MCP)
      └─ ask_question → 中文项目摘要
  ↓
[结果推送]
  ├─ feishu_ws_client: 卡片消息 + 图片上传 + emoji reaction
  └─ webhook: 群 Webhook 推送
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `run_bot.py` | 机器人启动入口（WebSocket 长连接） |
| `feishu_ws_client.py` | 飞书 WebSocket 客户端，处理消息事件、卡片回复、图片上传 |
| `webhook.py` | 飞书 Webhook 单向推送（Markdown → 卡片） |
| `analyzer_sdk.py` | SDK 直调分析器，Deep → Notes → Quick 三步管道 |
| `analyzer.py` | CLI 分析器（subprocess 调 claude 命令，备用方案） |
| `fetch_paper.py` | 论文获取主入口，协调 TeX/PDF 双路径 |
| `tex_fetcher.py` | arXiv TeX 源码下载与主文件识别 |
| `tex_converter.py` | LaTeX 展平 + Pandoc 转换 + 图片处理 |
| `hf_daily_papers.py` | HuggingFace 每日论文定时分析（支持并发） |
| `huggingface.py` | HuggingFace Papers API 数据获取 |
| `url_parser.py` | URL 解析（arXiv / CVF / HuggingFace / GitHub） |
| `deepwiki_client.py` | DeepWiki MCP 客户端，GitHub 仓库中文摘要 |
| `config.py` | 环境变量配置管理 |
| `state.py` | 处理状态持久化（并发安全，文件锁） |

## 输出结构

```
papers/{paper_id}/
├── {paper_id}.md              # 原始 Markdown（论文全文）
├── {paper_id}_metadata.json   # 论文元数据
├── {paper_id}_deep.md         # 深度分析
├── {paper_id}_notes.md        # 结构化笔记
├── {paper_id}_quick.md        # 速览摘要（推送到飞书）
└── images/                    # 所有图片（PNG 格式）
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_APP_ID` | 飞书应用 ID | — |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | — |
| `FEISHU_WEBHOOK_URL` | 飞书群 Webhook（可选） | — |
| `ANTHROPIC_API_KEY` | Anthropic API Key | — |
| `ANTHROPIC_MODEL` | 分析用模型 | `claude-sonnet-4-20250514` |
| `ANTHROPIC_BASE_URL` | 自定义 API 端点（兼容 z.ai 等） | — |
| `ANALYSIS_TIMEOUT` | 单篇分析超时（秒） | `600` |
| `DEEPWIKI_MCP_URL` | DeepWiki MCP 服务端点 | `https://mcp.deepwiki.com/mcp` |
| `HF_PAPERS_SCHEDULE_TIME` | HF 定时推送时间 | `09:00` |
| `MINERU_GPU_DEVICE` | MinerU GPU 设备号 | `0` |
| `MINERU_BACKEND` | MinerU 后端 | `pipeline` |

## 依赖

### Python 包（pyproject.toml）

核心：`httpx`, `python-dotenv`, `lark-oapi`, `pypandoc`

可选（`--extra full`）：`mineru[all]`, `schedule`, `faster-whisper`

### 系统工具

- **pandoc** — LaTeX → Markdown 转换
- **ImageMagick** 7.1+ — PDF 图片转 PNG

## License

MIT
