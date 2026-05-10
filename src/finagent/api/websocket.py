"""
WebSocket 实时评测进度推送

提供评测进度的实时推送功能，支持：
- 评测状态变更通知
- 三阶段流水线进度更新
- 任务级完成通知
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # evaluation_id -> set of WebSocket connections
        self._connections: dict[str, set] = {}
        self._lock = asyncio.Lock()

    async def connect(self, evaluation_id: str, websocket):
        async with self._lock:
            if evaluation_id not in self._connections:
                self._connections[evaluation_id] = set()
            self._connections[evaluation_id].add(websocket)
        logger.info("WebSocket connected: eval=%s", evaluation_id)

    async def disconnect(self, evaluation_id: str, websocket):
        async with self._lock:
            if evaluation_id in self._connections:
                self._connections[evaluation_id].discard(websocket)
                if not self._connections[evaluation_id]:
                    del self._connections[evaluation_id]

    async def broadcast(self, evaluation_id: str, message: dict):
        """广播消息给指定评测的所有连接"""
        if evaluation_id not in self._connections:
            return
        dead = set()
        for ws in self._connections[evaluation_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        async with self._lock:
            self._connections[evaluation_id] -= dead

    async def broadcast_all(self, message: dict):
        """广播给所有连接"""
        for eval_id in list(self._connections.keys()):
            await self.broadcast(eval_id, message)

    def active_connections(self, evaluation_id: str) -> int:
        return len(self._connections.get(evaluation_id, set()))


# Global singleton
manager = ConnectionManager()


# ============ 消息类型 ============

def progress_message(evaluation_id: str, phase: str, progress: float, stage: str, message: str = "") -> dict:
    """构建进度消息"""
    return {
        "type": "progress",
        "evaluation_id": evaluation_id,
        "current_phase": phase,
        "progress": progress,
        "stage": stage,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }


def status_message(evaluation_id: str, status: str, result: dict | None = None) -> dict:
    """构建状态变更消息"""
    return {
        "type": "status_change",
        "evaluation_id": evaluation_id,
        "status": status,
        "result": result,
        "timestamp": datetime.now().isoformat(),
    }


def task_message(evaluation_id: str, task_id: str, dimension: str, score: float | None = None) -> dict:
    """构建任务完成消息"""
    return {
        "type": "task_completed",
        "evaluation_id": evaluation_id,
        "task_id": task_id,
        "dimension": dimension,
        "score": score,
        "timestamp": datetime.now().isoformat(),
    }


def error_message(evaluation_id: str, error: str) -> dict:
    """构建错误消息"""
    return {
        "type": "error",
        "evaluation_id": evaluation_id,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    }
