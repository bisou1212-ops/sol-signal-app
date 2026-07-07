"""시장 상태 및 변동성 레벨 판별"""
import pandas as pd

from app.strategy.base import Direction


def get_market_state(df: pd.DataFrame, direction: Direction) -> str:
    last = df.iloc[-1]
    adx = last["adx"]
    if pd.isna(adx) or adx < 20:
        return "횡보"
    if direction == Direction.LONG:
        return "상승 추세"
    if direction == Direction.SHORT:
        return "하락 추세"
    return "횡보"


def get_volatility_state(df: pd.DataFrame) -> str:
    if len(df) < 20 or pd.isna(df["bb_width"].iloc[-1]):
        return "보통"
    width = df["bb_width"].iloc[-1]
    history = df["bb_width"].iloc[-100:] if len(df) >= 100 else df["bb_width"]
    low, high = history.quantile(0.33), history.quantile(0.66)
    if width <= low:
        return "낮음"
    if width >= high:
        return "높음"
    return "보통"
