"""캔들 데이터 수집 및 DataFrame 변환"""
import asyncio

import pandas as pd

from app.api.bitget_client import bitget_client
from app.config import settings

# 내부 표기 -> Bitget granularity 표기
GRANULARITY_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
}

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "quote_volume"]


def _to_dataframe(raw: list[list[str]]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(raw, columns=COLUMNS[: len(raw[0])])
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms", utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


async def fetch_candles_df(tf: str, symbol: str = None, limit: int = 200) -> pd.DataFrame:
    """단일 시간봉 캔들을 DataFrame으로 반환 (시간 오름차순)"""
    granularity = GRANULARITY_MAP.get(tf, tf)
    raw = await bitget_client.get_candles(symbol=symbol, granularity=granularity, limit=limit)
    return _to_dataframe(raw)


async def fetch_multi_tf(symbol: str = None, limit: int = 200) -> dict[str, pd.DataFrame]:
    """전략에 필요한 전 시간봉(5m/15m/1h/4h) 캔들을 병렬로 수집 (지연시간 최소화)"""
    tfs = {
        "ltf": settings.ltf_ref,
        "main": settings.main_tf,
        "htf1": settings.htf_1,
        "htf2": settings.htf_2,
    }
    keys = list(tfs.keys())
    dfs = await asyncio.gather(*(fetch_candles_df(tfs[k], symbol=symbol, limit=limit) for k in keys))
    return dict(zip(keys, dfs))
