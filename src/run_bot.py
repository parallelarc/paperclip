#!/usr/bin/env python3
"""飞书论文机器人启动脚本（纯 WebSocket 模式）"""
import logging
import signal
import sys
import time

from .feishu_ws_client import start_ws_thread, stop_ws_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Lark SDK 会自己加 handler 并 propagate 到 root，导致重复输出
# 清掉 SDK 自带 handler，统一走 root logger 的格式和级别控制
_lark_logger = logging.getLogger("Lark")
_lark_logger.handlers.clear()
_lark_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def main() -> None:
    """启动飞书 WebSocket 机器人"""
    logger.info("正在启动飞书论文机器人...")

    thread = start_ws_thread()
    if not thread:
        logger.error("启动失败：请检查 FEISHU_APP_ID 和 FEISHU_APP_SECRET 配置")
        sys.exit(1)

    logger.info("机器人已启动，等待飞书消息...")

    def signal_handler(sig):
        logger.info("收到退出信号，正在关闭...")
        stop_ws_client()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None)


if __name__ == "__main__":
    main()
