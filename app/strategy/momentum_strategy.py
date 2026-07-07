"""② 모멘텀 전략: RSI, MACD, Stochastic RSI"""
import pandas as pd

from app.strategy.base import Direction, StrategyResult, clamp


def evaluate_momentum(df: pd.DataFrame) -> StrategyResult:
    last = df.iloc[-1]
    prev = df.iloc[-2]
    reasons: list[str] = []
    long_score = 0.0
    short_score = 0.0

    rsi = last["rsi"]
    macd_hist, macd_hist_prev = last["macd_hist"], prev["macd_hist"]
    k, d = last["stoch_rsi_k"], last["stoch_rsi_d"]

    if pd.isna(rsi) or pd.isna(macd_hist) or pd.isna(k):
        return StrategyResult("모멘텀", 0.0, Direction.NEUTRAL, ["지표 데이터 부족"])

    # RSI (최대 35점) - 과매수/과매도 근접 시 반대 방향 감점
    if 50 < rsi < 70:
        long_score += 35
        reasons.append(f"RSI {rsi:.1f} (상승 모멘텀)")
    elif 30 < rsi < 50:
        short_score += 35
        reasons.append(f"RSI {rsi:.1f} (하락 모멘텀)")
    elif rsi >= 70:
        long_score += 15
        reasons.append(f"RSI {rsi:.1f} (과매수 경계)")
    elif rsi <= 30:
        short_score += 15
        reasons.append(f"RSI {rsi:.1f} (과매도 경계)")

    # MACD 히스토그램 (최대 35점)
    if macd_hist > 0:
        long_score += 25 if macd_hist > macd_hist_prev else 15
        reasons.append("MACD 히스토그램 양전환/증가" if macd_hist > macd_hist_prev else "MACD 양수 유지")
    elif macd_hist < 0:
        short_score += 25 if macd_hist < macd_hist_prev else 15
        reasons.append("MACD 히스토그램 음전환/감소" if macd_hist < macd_hist_prev else "MACD 음수 유지")

    # Stochastic RSI (최대 30점)
    if k > d and k < 80:
        long_score += 30
        reasons.append(f"StochRSI %K({k:.1f}) > %D({d:.1f}) 골든크로스")
    elif k < d and k > 20:
        short_score += 30
        reasons.append(f"StochRSI %K({k:.1f}) < %D({d:.1f}) 데드크로스")
    elif k >= 80:
        reasons.append("StochRSI 과매수 구간")
    elif k <= 20:
        reasons.append("StochRSI 과매도 구간")

    if long_score > short_score:
        return StrategyResult("모멘텀", clamp(long_score), Direction.LONG, reasons)
    elif short_score > long_score:
        return StrategyResult("모멘텀", clamp(short_score), Direction.SHORT, reasons)
    return StrategyResult("모멘텀", clamp(max(long_score, short_score)), Direction.NEUTRAL, reasons)
