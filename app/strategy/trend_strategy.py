"""① 추세 전략: EMA50, EMA200, ADX"""
import pandas as pd

from app.strategy.base import Direction, StrategyResult, clamp


def evaluate_trend(df: pd.DataFrame) -> StrategyResult:
    last = df.iloc[-1]
    reasons: list[str] = []
    score = 0.0
    direction = Direction.NEUTRAL

    close, ema50, ema200, adx = last["close"], last["ema50"], last["ema200"], last["adx"]

    if pd.isna(ema50) or pd.isna(ema200) or pd.isna(adx):
        return StrategyResult("추세", 0.0, Direction.NEUTRAL, ["지표 데이터 부족"])

    # 구조적 방향성 (최대 50점)
    if close > ema50 > ema200:
        direction = Direction.LONG
        score += 50
        reasons.append("가격 > EMA50 > EMA200 (상승 정배열)")
    elif close < ema50 < ema200:
        direction = Direction.SHORT
        score += 50
        reasons.append("가격 < EMA50 < EMA200 (하락 역배열)")
    else:
        reasons.append("EMA 배열 불명확 (횡보 가능성)")

    # EMA50 기울기 (최대 20점)
    ema50_prev = df["ema50"].iloc[-6] if len(df) > 6 else ema50
    slope = (ema50 - ema50_prev) / ema50_prev * 100 if ema50_prev else 0
    slope_score = clamp(abs(slope) * 40, 0, 20)
    score += slope_score
    if direction == Direction.LONG and slope < 0:
        score -= slope_score  # 방향 불일치 시 감점 취소
        reasons.append("EMA50 기울기 하락 (추세 약화)")
    elif direction == Direction.SHORT and slope > 0:
        score -= slope_score
        reasons.append("EMA50 기울기 상승 (추세 약화)")
    else:
        reasons.append(f"EMA50 기울기 {slope:.2f}% (추세 방향 일치)")

    # ADX 강도 (최대 30점)
    if adx >= 25:
        adx_score = clamp((adx - 25) / 25 * 30 + 15, 0, 30)
        reasons.append(f"ADX {adx:.1f} (추세 강함)")
    elif adx >= 20:
        adx_score = 10
        reasons.append(f"ADX {adx:.1f} (추세 형성 중)")
    else:
        adx_score = 0
        direction = Direction.NEUTRAL if adx < 15 else direction
        reasons.append(f"ADX {adx:.1f} (횡보/추세 약함)")
    score += adx_score

    return StrategyResult("추세", clamp(score), direction, reasons)
