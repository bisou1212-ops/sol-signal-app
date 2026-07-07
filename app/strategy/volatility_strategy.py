"""⑤ 변동성 전략: ATR, 볼린저밴드, 켈트너채널"""
import pandas as pd

from app.strategy.base import Direction, StrategyResult, clamp


def evaluate_volatility(df: pd.DataFrame) -> StrategyResult:
    last = df.iloc[-1]
    reasons: list[str] = []
    long_score = 0.0
    short_score = 0.0

    close = last["close"]
    atr, bb_upper, bb_lower, bb_mid = last["atr"], last["bb_upper"], last["bb_lower"], last["bb_mid"]
    kc_upper, kc_lower = last["kc_upper"], last["kc_lower"]

    if pd.isna(atr) or pd.isna(bb_upper) or pd.isna(kc_upper):
        return StrategyResult("변동성", 0.0, Direction.NEUTRAL, ["지표 데이터 부족"])

    # ATR 확장 여부 (최대 30점) - 변동성이 커질 때 추세 신뢰도 상승
    atr_ma = df["atr"].iloc[-20:].mean() if len(df) >= 20 else atr
    atr_expanding = atr > atr_ma
    vol_score = clamp((atr / atr_ma - 1) * 100, 0, 30) if atr_ma else 0
    if atr_expanding:
        reasons.append(f"ATR 확장 중 (현재 {atr:.4f} > 평균 {atr_ma:.4f})")
    else:
        reasons.append(f"ATR 축소 중 (현재 {atr:.4f} < 평균 {atr_ma:.4f})")

    # 볼린저 밴드 스퀴즈 (BB가 KC 안쪽) - 돌파 임박 신호
    squeeze = bb_upper < kc_upper and bb_lower > kc_lower
    if squeeze:
        reasons.append("볼린저밴드-켈트너채널 스퀴즈 (변동성 수축, 돌파 임박)")

    # 밴드 위치 기반 방향 (최대 40점)
    if close >= bb_upper:
        long_score += 40
        reasons.append("가격이 볼린저 상단 돌파/근접")
    elif close <= bb_lower:
        short_score += 40
        reasons.append("가격이 볼린저 하단 돌파/근접")
    elif close > bb_mid:
        long_score += 15
        reasons.append("가격이 중심선 위 (약한 상승 편향)")
    elif close < bb_mid:
        short_score += 15
        reasons.append("가격이 중심선 아래 (약한 하락 편향)")

    # ATR 확장이 방향성을 뒷받침할 때만 가산 (최대 30점)
    if atr_expanding:
        if long_score >= short_score:
            long_score += vol_score
        else:
            short_score += vol_score
    else:
        # 스퀴즈 중이면 방향 확정 보류 (점수 축소)
        long_score *= 0.7
        short_score *= 0.7

    if long_score > short_score:
        return StrategyResult("변동성", clamp(long_score), Direction.LONG, reasons)
    elif short_score > long_score:
        return StrategyResult("변동성", clamp(short_score), Direction.SHORT, reasons)
    return StrategyResult("변동성", clamp(max(long_score, short_score)), Direction.NEUTRAL, reasons)
