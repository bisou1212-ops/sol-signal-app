"""전체 지표 통합 계산"""
import pandas as pd

from app.indicators.momentum import add_momentum_indicators
from app.indicators.trend import add_trend_indicators
from app.indicators.volatility import add_volatility_indicators
from app.indicators.volume import add_volume_indicators


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV DataFrame에 전 지표를 추가하여 반환"""
    if df.empty:
        return df
    df = add_trend_indicators(df)
    df = add_momentum_indicators(df)
    df = add_volume_indicators(df)
    df = add_volatility_indicators(df)
    return df


def compute_multi_tf(tf_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """{tf명: OHLCV df} -> {tf명: 지표 포함 df}"""
    return {tf: compute_indicators(df) for tf, df in tf_data.items()}
