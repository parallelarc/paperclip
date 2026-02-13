# Paperclip

飞书论文分析机器人 - 自动获取、分析并推送 Hugging Face 每日论文到飞书群聊。

## 功能特性

- **每日论文推送**: 定时获取 Hugging Face 最新论文并推送到飞书
- **PDF 解析**: 使用 MinerU 进行高质量 PDF 文档解析
- **论文分析**: 支持快速/详细两种分析模式
- **WebSocket 长连接**: 基于飞书事件订阅的实时通信

## 安装

```bash
pip install -e .
```

或使用 uv：

```bash
uv pip install -e .
```

## 配置

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

### 核心配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `FEISHU_APP_ID` | 飞书应用 ID | - |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | - |
| `HF_PAPERS_SCHEDULE_TIME` | 每日推送时间 | 09:00 |
| `ANALYSIS_TIMEOUT` | 论文分析超时(秒) | 600 |
| `ANALYSIS_FORMAT` | 分析格式 (quick/detailed) | quick |
| `MINERU_GPU_DEVICE` | GPU 设备编号 (-1=仅CPU) | 0 |
| `MINERU_BACKEND` | MinerU 后端类型 | hybrid-auto-engine |

### MinerU 后端选项

`MINERU_BACKEND` 支持以下选项：

| 选项 | 说明 |
|------|------|
| `pipeline` | 基础流水线模式 |
| `hybrid-auto-engine` | 混合自动引擎（推荐） |
| `hybrid-http-client` | 混合 HTTP 客户端 |
| `vlm-auto-engine` | VLM 自动引擎 |
| `vlm-http-client` | VLM HTTP 客户端 |

## 使用

### 启动机器人

```bash
python -m paperclip.run_bot
```

### 手动获取论文

```python
from paperclip.huggingface import get_daily_papers
papers = get_daily_papers("2024-02-05")
```

### 分析单篇论文

```python
from paperclip.analyzer import analyze_paper
result = analyze_paper("https://arxiv.org/abs/2401.00001")
```

## 项目结构

```
paperclip/
├── run_bot.py          # 启动入口
├── config.py           # 配置管理
├── feishu_ws_client.py # WebSocket 客户端
├── hf_daily_papers.py  # Hugging Face 论文获取
├── fetch_paper.py      # PDF 下载与解析
├── analyzer.py         # 论文分析器
├── webhook.py          # Webhook 消息发送
├── state.py            # 状态管理
└── .env.example        # 配置模板
```

## 依赖

- `httpx` - HTTP 客户端
- `python-dotenv` - 环境变量管理
- `mineru[all]` - PDF 解析
- `schedule` - 任务调度
- `lark-oapi` - 飞书开放平台 SDK

## 许可证

MIT
