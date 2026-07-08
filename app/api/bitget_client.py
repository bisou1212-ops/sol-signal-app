"""Bitget Futures API 클라이언트 (v2)"""
import asyncio
import base64
import hashlib
import hmac
import time
from typing import Any

import httpx

from app.config import settings

MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 0.5


class BitgetClient:
    """Bitget USDT-FUTURES REST API 클라이언트"""

    def __init__(self) -> None:
        self.base_url = settings.bitget_base_url
        self.api_key = settings.bitget_api_key
        self.api_secret = settings.bitget_api_secret
        self.passphrase = settings.bitget_passphrase
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    # ---------- 인증 ----------
    def _sign(self, timestamp: str, method: str, path: str, query: str, body: str) -> str:
        message = f"{timestamp}{method.upper()}{path}{query}{body}"
        mac = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        )
        return base64.b64encode(mac.digest()).decode()

    def _auth_headers(self, method: str, path: str, query: str = "", body: str = "") -> dict:
        timestamp = str(int(time.time() * 1000))
        sign = self._sign(timestamp, method, path, query, body)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": "ko-KR",
        }

    # ---------- 공통 재시도 헬퍼 ----------
    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.request(method, path, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, httpx.TransportError) as e:
                last_err = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        raise last_err

    # ---------- 공개 API (인증 불필요) ----------
    async def get_candles(
        self,
        symbol: str = None,
        granularity: str = "15min",
        limit: int = 200,
        end_time: str = None,
    ) -> list[list[str]]:
        """캔들(K라인) 조회
        granularity: 1min,5min,15min,30min,1h,4h,1day 등 (Bitget v2 공식 표기법)
        end_time: 이 시각(ms) 이전 데이터 조회 (과거 데이터 페이지네이션용)
        """
        path = "/api/v2/mix/market/candles"
        params = {
            "symbol": symbol or settings.symbol,
            "productType": settings.product_type,
            "granularity": granularity,
            "limit": str(limit),
        }
        if end_time:
            params["endTime"] = end_time
        data = await self._request("GET", path, params=params)
        return data.get("data", [])

    async def get_ticker(self, symbol: str = None) -> dict[str, Any]:
        """실시간 시세 조회"""
        path = "/api/v2/mix/market/ticker"
        params = {"symbol": symbol or settings.symbol, "productType": settings.product_type}
        data = await self._request("GET", path, params=params)
        items = data.get("data", [])
        return items[0] if items else {}

    # ---------- 인증 필요 API (추후 사용) ----------
    async def get_account(self, symbol: str = None) -> dict[str, Any]:
        """계정/포지션 정보 (선물)"""
        path = "/api/v2/mix/account/account"
        params = {
            "symbol": symbol or settings.symbol,
            "productType": settings.product_type,
            "marginCoin": "USDT",
        }
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        headers = self._auth_headers("GET", path, query)
        resp = await self._client.get(path, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()


bitget_client = BitgetClient()
