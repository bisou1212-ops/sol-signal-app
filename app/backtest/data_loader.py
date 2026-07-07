"""백테스트 데이터 로더: 15분봉을 API로 수집 후 1H/4H는 리샘플로 생성(시간 정합 보장)"""
import pandas as pd

from app.data.candle_store import fetch_candles_df
from app.indicators.engine import compute_indicators

RESAMPLE_RULE = {"htf1": "1h", "htf2": "4h"}


def _resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    resampled = (
        df.set_index("timestamp")
        .resample(rule)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
        .reset_index()
    )
    return resampled


async def load_backtest_data(symbol: str = None, limit: int = 1000) -> dict[str, pd.DataFrame]:
    """메인(15분) 캔들을 수집하고 상위 시간봉은 리샘플하여 지표까지 계산"""
    main_raw = await fetch_candles_df("15m", symbol=symbol, limit=limit)
    htf1_raw = _resample_ohlcv(main_raw, RESAMPLE_RULE["htf1"])
    htf2_raw = _resample_ohlcv(main_raw, RESAMPLE_RULE["htf2"])

    return {
        "main": compute_indicators(main_raw),
        "htf1": compute_indicators(htf1_raw),
        "htf2": compute_indicators(htf2_raw),
    }
