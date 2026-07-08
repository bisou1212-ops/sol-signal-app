"""캔들 데이터 수집 및 DataFrame 변환"""
import asyncio

import pandas as pd

from app.api.bitget_client import bitget_client
from app.config import settings

# 내부 표기 -> Bitget v2 granularity 표기
# (공식 문서 기준: 1min/5min/15min/30min/1h/4h/1day 등. "15m","1H" 같은 표기는 400 에러 원인이었음)
GRANULARITY_MAP = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
}

BITGET_MAX_LIMIT = 1000  # Bitget 캔들 API 1회 요청 최대치

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "quote_volume"]


def _to_dataframe(raw: list[list[str]]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(raw, columns=COLUMNS[: len(raw[0])])
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


async def fetch_candles_df(tf: str, symbol: str = None, limit: int = 200) -> pd.DataFrame:
    """단일 시간봉 캔들을 DataFrame으로 반환 (시간 오름차순). limit이 1000 초과면 자동으로 나눠 요청."""
    granularity = GRANULARITY_MAP.get(tf, tf)

    if limit <= BITGET_MAX_LIMIT:
        raw = await bitget_client.get_candles(symbol=symbol, granularity=granularity, limit=limit)
        return _to_dataframe(raw)

    # 1000개 초과 요청 -> endTime 커서로 과거 방향 페이지네이션
    all_raw: list[list[str]] = []
    end_time: str | None = None
    remaining = limit
    while remaining > 0:
        page_limit = min(BITGET_MAX_LIMIT, remaining)
        page = await bitget_client.get_candles(
            symbol=symbol, granularity=granularity, limit=page_limit, end_time=end_time,
        )
        if not page:
            break
        all_raw.extend(page)
        oldest_ts = min(int(row[0]) for row in page)
        end_time = str(oldest_ts - 1)
        remaining -= len(page)
        if len(page) < page_limit:  # 더 이상 과거 데이터 없음
            break

    return _to_dataframe(all_raw)


async def fetch_multi_tf(symbol: str = None, limit: int = 200) -> dict[str, pd.DataFrame]:
    """전략에 필요한 전 시간봉 캔들을 병렬로 수집 (지연시간 최소화)"""
    tfs = {
        "ltf": settings.ltf_ref,
        "main": settings.main_tf,
        "htf1": settings.htf_1,
        "htf2": settings.htf_2,
    }
    keys = list(tfs.keys())
    dfs = await asyncio.gather(*(fetch_candles_df(tfs[k], symbol=symbol, limit=limit) for k in keys))
    return dict(zip(keys, dfs))
