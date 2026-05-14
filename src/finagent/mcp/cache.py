"""
外部数据缓存模块

提供内存和 Redis 缓存支持，用于缓存外部数据源结果。
对应数据质量治理方案 - 阶段 3
"""

import json
import time
from dataclasses import dataclass
from typing import Any, TypeVar, Generic
from abc import ABC, abstractmethod

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    value: T
    expires_at: float
    created_at: float


class CacheBackend(ABC, Generic[T]):
    """缓存后端抽象基类"""

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """获取缓存值"""
        pass

    @abstractmethod
    async def set(self, key: str, value: T, ttl: int) -> None:
        """设置缓存值"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """清空缓存"""
        pass


class MemoryCacheBackend(CacheBackend[T]):
    """内存缓存后端"""

    def __init__(self):
        self._cache: dict[str, CacheEntry[T]] = {}

    async def get(self, key: str) -> T | None:
        entry = self._cache.get(key)
        if entry is None:
            return None

        if time.time() > entry.expires_at:
            # 过期删除
            del self._cache[key]
            return None

        return entry.value

    async def set(self, key: str, value: T, ttl: int) -> None:
        now = time.time()
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=now + ttl,
            created_at=now,
        )

    async def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        entry = self._cache.get(key)
        if entry is None:
            return False
        if time.time() > entry.expires_at:
            del self._cache[key]
            return False
        return True

    async def clear(self) -> None:
        self._cache.clear()

    def get_stats(self) -> dict:
        """获取缓存统计"""
        now = time.time()
        total = len(self._cache)
        expired = sum(1 for e in self._cache.values() if now > e.expires_at)
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
        }


class DataCache:
    """
    数据缓存

    支持多级缓存策略：
    - L1: 内存缓存（快速访问）
    - L2: Redis 缓存（分布式共享）
    """

    def __init__(
        self,
        default_ttl: int = 300,  # 默认 5 分钟
        backend: CacheBackend | None = None,
    ):
        self.default_ttl = default_ttl
        self._backend = backend or MemoryCacheBackend()

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        return await self._backend.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """设置缓存值"""
        await self._backend.set(key, value, ttl or self.default_ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        return await self._backend.delete(key)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self._backend.exists(key)

    async def clear(self) -> None:
        """清空缓存"""
        await self._backend.clear()

    def get_stats(self) -> dict:
        """获取缓存统计"""
        if hasattr(self._backend, "get_stats"):
            return self._backend.get_stats()
        return {}

    @staticmethod
    def make_key(*parts: str) -> str:
        """
        构建缓存键

        用法:
            key = DataCache.make_key("yahoo", "AAPL", "price")
        """
        return ":".join(parts)


class MCPDataCache:
    """
    MCP 数据专用缓存

    为 MCP 工具调用结果提供缓存支持。
    """

    def __init__(self, cache: DataCache | None = None):
        self._cache = cache or DataCache()

    def _make_tool_key(self, server: str, tool: str, args: dict) -> str:
        """构建工具调用缓存键"""
        # 将参数排序后序列化，确保相同的参数产生相同的键
        args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
        return DataCache.make_key("mcp", server, tool, args_str)

    async def get_tool_result(
        self,
        server: str,
        tool: str,
        args: dict,
    ) -> Any | None:
        """获取工具调用缓存结果"""
        key = self._make_tool_key(server, tool, args)
        return await self._cache.get(key)

    async def set_tool_result(
        self,
        server: str,
        tool: str,
        args: dict,
        result: Any,
        ttl: int | None = None,
    ) -> None:
        """设置工具调用缓存结果"""
        key = self._make_tool_key(server, tool, args)
        await self._cache.set(key, result, ttl)

    async def invalidate_server(self, server: str) -> int:
        """
        使某个服务器的所有缓存失效

        当服务器故障或数据更新时使用。
        """
        # 内存缓存需要遍历所有键
        if isinstance(self._cache._backend, MemoryCacheBackend):
            prefix = f"mcp:{server}:"
            keys_to_delete = [
                key for key in self._cache._backend._cache.keys()
                if key.startswith(prefix)
            ]
            for key in keys_to_delete:
                await self._cache.delete(key)
            return len(keys_to_delete)
        return 0

    async def invalidate_tool(self, server: str, tool: str) -> int:
        """使某个工具的所有缓存失效"""
        if isinstance(self._cache._backend, MemoryCacheBackend):
            prefix = f"mcp:{server}:{tool}:"
            keys_to_delete = [
                key for key in self._cache._backend._cache.keys()
                if key.startswith(prefix)
            ]
            for key in keys_to_delete:
                await self._cache.delete(key)
            return len(keys_to_delete)
        return 0

    def get_stats(self) -> dict:
        """获取缓存统计"""
        return self._cache.get_stats()
