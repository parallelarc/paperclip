"""
配置管理
"""
import os
from pathlib import Path
from dotenv import load_dotenv

ENV_DIR = Path(__file__).parent.parent
load_dotenv(ENV_DIR / ".env", override=True)


class Settings:
    """配置项"""

    # 目录
    env_dir = ENV_DIR
    state_dir = ENV_DIR / "state"

    # 飞书 Webhook
    feishu_webhook_url = os.getenv("FEISHU_WEBHOOK_URL")

    # 飞书开放平台应用凭证
    feishu_app_id = os.getenv("FEISHU_APP_ID")
    feishu_app_secret = os.getenv("FEISHU_APP_SECRET")

    # 事件订阅配置（可选）
    feishu_encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")
    feishu_verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")

    # API 配置
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8000"))

    # Hugging Face Papers
    hf_papers_base_url = "https://huggingface.co/papers/date"
    hf_paper_api_url = "https://huggingface.co/api/papers/{}"
    hf_papers_schedule_time = os.getenv("HF_PAPERS_SCHEDULE_TIME", "09:00")

    # 论文分析
    analysis_timeout = int(os.getenv("ANALYSIS_TIMEOUT", "600"))
    analysis_format = os.getenv("ANALYSIS_FORMAT", "quick")

    # GPU 设备配置
    mineru_gpu_device = os.getenv("MINERU_GPU_DEVICE", "0")

    # MinerU 后端配置
    mineru_backend = os.getenv("MINERU_BACKEND", "pipeline")

    # DeepWiki MCP
    deepwiki_mcp_url = os.getenv("DEEPWIKI_MCP_URL", "https://mcp.deepwiki.com/mcp")

    # Anthropic API
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", "")
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "glm-5")


settings = Settings()
