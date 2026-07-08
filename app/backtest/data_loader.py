"""백테스트 데이터 로더: 3분봉을 API로 수집 후 15분봉은 리샘플로 생성(시간 정합 보장)"""
import pandas as pd

from app.config import settings
from app.data.candle_store import fetch_candles_df
from app.indicators.engine import compute_indicators

TREND_RESAMPLE_RULE = "15min"


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


async def load_backtest_data(symbol: str = None, limit: int = 3000) -> dict[str, pd.DataFrame]:
    """메인(3분) 캔들을 수집하고 추세 필터(15분)는 리샘플하여 지표까지 계산.
    15분봉 EMA200 워밍업(약 210봉=52.5시간)을 확보하려면 limit을 충분히 크게 잡아야 한다."""
    main_raw = await fetch_candles_df(settings.main_tf, symbol=symbol, limit=limit)
    trend_raw = _resample_ohlcv(main_raw, TREND_RESAMPLE_RULE)

    trend_df = compute_indicators(trend_raw)
    return {
        "main": compute_indicators(main_raw),
        "htf1": trend_df,
        "htf2": trend_df,
    }
