# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                        # install base deps (no MinerU/GPU)
uv sync --extra full           # add MinerU OCR, schedule, faster-whisper

python -m src.run_bot          # start Feishu WebSocket bot (long-lived)
python -m src.fetch_paper 2401.08689                # fetch single paper by arXiv ID
python -m src.fetch_paper https://arxiv.org/abs/2401.08689  # or full URL
python -m src.hf_daily_papers --limit 5             # batch analyze HF papers
python -m src.hf_daily_papers --schedule            # daily scheduled run (default 09:00)
```

System dependencies: `pandoc` (LaTeX→Markdown, bundled via pypandoc_binary), `ImageMagick 7.1+` (PDF→PNG fallback).

## Architecture

Feishu chatbot that fetches academic papers from arXiv/HuggingFace/CVF and produces three-tier analysis (Deep → Notes → Quick). All source is in `src/` as a flat package.

### Data flow

```
Input (Feishu @bot / HF schedule / CLI)
  → arxiv.py: parse URL → paper ID
  → fetch_paper.py: dual-path download
      Path 1 (preferred): tex_fetcher.py + tex_converter.py → Pandoc
      Path 2 (fallback):  MinerU OCR from PDF
  → analyzer_sdk.py: three-step Anthropic API pipeline (Deep → Notes → Quick)
  → Delivery: feishu_ws_client.py (interactive cards) / webhook.py (async push)
```

### Key modules

- **fetch_paper.py** — Orchestrator. Chooses TeX vs PDF path, delegates to tex_fetcher or MinerU. CLI entry via `__main__`.
- **tex_fetcher.py** — Downloads arXiv `.tar.gz` e-print, extracts TeX source tree.
- **tex_converter.py** — Flattens `\input`/`\include`, preprocesses non-standard LaTeX, runs Pandoc, extracts figures (PDF→PNG via PyMuPDF).
- **analyzer_sdk.py** — Primary analyzer. Three serial Anthropic API calls using prompt templates from `.claude/skills/paper-reader/references/`. Results cached as `{paper_id}_deep/notes/quick.md` alongside the paper.
- **analyzer.py** — Backup analyzer that shells out to `claude` CLI with the paper-reader skill. Uses `--dangerously-skip-permissions`.
- **feishu_ws_client.py** — WebSocket bot. Handles incoming Feishu events via `lark_oapi`, replies with interactive cards, uploads inline images.
- **webhook.py** — Async one-way Feishu card push. Builds Feishu card schema 2.0 from markdown.
- **hf_daily_papers.py** — Fetches daily trending papers from HuggingFace API, batches analysis with concurrency control.
- **state.py** — File-based state with `fcntl.flock` for concurrency safety. Tracks processed paper IDs under `state/`.
- **config.py** — Single `Settings` class, all config from env vars via `.env`.
- **arxiv.py** — URL/ID parsing for arXiv, CVF, and HuggingFace paper URLs.

### Analysis pipeline

`analyzer_sdk.py` reads prompt templates from `.claude/skills/paper-reader/references/`:
- `paper-deep.md` → full analysis (16384 max output tokens)
- `paper-notes.md` → structured notes (8192 max)
- `paper-quick.md` → brief summary (4096 max)

Each step reads the previous step's output. Results are cached by paper_id; re-running skips already-analyzed steps.

### Configuration

All via `.env` (see `.env.example`). Key groups:

| Group | Variables | Notes |
|-------|-----------|-------|
| Feishu App | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` | Required for bot mode |
| Feishu Webhook | `FEISHU_WEBHOOK_URL` | Optional, for push mode |
| Anthropic API | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` | `ANTHROPIC_BASE_URL` supports third-party endpoints |
| Analysis | `ANALYSIS_TIMEOUT` (default 600), `ANALYSIS_FORMAT` (quick/notes/deep) | Controls LLM behavior |
| HF Schedule | `HF_PAPERS_SCHEDULE_TIME` (default 09:00) | Cron time for daily papers |

## Conventions

- No tests or linting setup exists.
- Chinese comments and docstrings are used throughout — maintain this convention when modifying existing files.
- The `analyzer_sdk.py` supports Anthropic-compatible APIs (e.g., z.ai) via `ANTHROPIC_BASE_URL` env var with `auth_token` parameter.
