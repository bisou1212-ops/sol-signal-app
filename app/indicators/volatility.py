"""변동성 지표: ATR, 볼린저밴드, 켈트너채널"""
import pandas as pd
import ta


def add_volatility_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["atr"] = ta.volatility.average_true_range(
        df["high"], df["low"], df["close"], window=14
    )

    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    kc = ta.volatility.KeltnerChannel(df["high"], df["low"], df["close"], window=20)
    df["kc_upper"] = kc.keltner_channel_hband()
    df["kc_mid"] = kc.keltner_channel_mband()
    df["kc_lower"] = kc.keltner_channel_lband()
    return df
