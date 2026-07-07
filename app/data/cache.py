"""메모리 캔들 캐시 (실시간 갱신용)"""
import asyncio
import time

import pandas as pd

from app.data.candle_store import fetch_multi_tf


class CandleCache:
    """멀티 타임프레임 캔들을 메모리에 유지하고 주기적으로 갱신"""

    def __init__(self, refresh_seconds: int = 15) -> None:
        self.refresh_seconds = refresh_seconds
        self.data: dict[str, pd.DataFrame] = {}
        self.last_updated: float = 0.0
        self._lock = asyncio.Lock()

    async def refresh(self, symbol: str = None) -> None:
        async with self._lock:
            self.data = await fetch_multi_tf(symbol=symbol)
            self.last_updated = time.time()

    def is_stale(self) -> bool:
        return (time.time() - self.last_updated) > self.refresh_seconds

    async def get(self, symbol: str = None) -> dict[str, pd.DataFrame]:
        if not self.data or self.is_stale():
            await self.refresh(symbol=symbol)
        return self.data


candle_cache = CandleCache()
