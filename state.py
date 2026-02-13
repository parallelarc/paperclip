"""
状态管理 - 记录已处理的论文（支持并发安全）
"""
import fcntl
from pathlib import Path
from .config import settings


class StateManager:
    """状态管理器（并发安全）"""

    def __init__(self, name: str = "processed"):
        """
        初始化状态管理器

        Args:
            name: 状态文件名称（不含扩展名）
        """
        self.name = name
        self.state_dir = settings.state_dir
        self.state_file = self.state_dir / f"{name}.txt"
        self._ensure_dir()

    def _ensure_dir(self):
        """确保状态目录存在"""
        self.state_dir.mkdir(exist_ok=True)

    def get_processed(self) -> set:
        """获取已处理的 ID 集合"""
        if self.state_file.exists():
            content = self.state_file.read_text().strip()
            return set(filter(None, content.split("\n"))) if content else set()
        return set()

    def is_processed(self, item_id: str) -> bool:
        """检查是否已处理"""
        return item_id in self.get_processed()

    def mark_processed(self, item_id: str):
        """标记为已处理（并发安全）"""
        # 使用文件锁保证并发安全
        processed = self.get_processed()
        if item_id in processed:
            return  # 已经处理过，直接返回

        processed.add(item_id)

        # 以追加模式写入，避免覆盖
        with open(self.state_file, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取排他锁
            try:
                f.write(f"{item_id}\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁

    def mark_processed_many(self, item_ids: list):
        """批量标记为已处理（并发安全）"""
        processed = self.get_processed()
        new_ids = [id for id in item_ids if id not in processed]

        if not new_ids:
            return

        # 以追加模式写入新 ID
        with open(self.state_file, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                for item_id in new_ids:
                    f.write(f"{item_id}\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def clear(self):
        """清空状态"""
        if self.state_file.exists():
            self.state_file.unlink()
