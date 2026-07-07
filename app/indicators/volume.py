"""거래량 지표: VWAP(일 단위 앵커), OBV, 거래량 평균"""
import numpy as np
import pandas as pd
import ta


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 일(UTC) 단위로 리셋되는 앵커드 VWAP
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    day = df["timestamp"].dt.floor("D")
    tp_vol = typical_price * df["volume"]
    cum_tp_vol = tp_vol.groupby(day).cumsum()
    cum_vol = df["volume"].groupby(day).cumsum()
    df["vwap"] = np.where(cum_vol > 0, cum_tp_vol / cum_vol, np.nan)

    df["obv"] = ta.volume.on_balance_volume(df["close"], df["volume"])
    df["volume_ma20"] = df["volume"].rolling(window=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma20"]
    return df
