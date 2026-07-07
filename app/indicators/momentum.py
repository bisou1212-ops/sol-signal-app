"""모멘텀 지표: RSI, MACD, Stochastic RSI"""
import pandas as pd
import ta


def add_momentum_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)

    macd = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    stoch_rsi = ta.momentum.StochRSIIndicator(df["close"], window=14, smooth1=3, smooth2=3)
    df["stoch_rsi_k"] = stoch_rsi.stochrsi_k() * 100
    df["stoch_rsi_d"] = stoch_rsi.stochrsi_d() * 100
    return df
