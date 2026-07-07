"""③ 거래량 전략: VWAP, OBV, Volume"""
import pandas as pd

from app.strategy.base import Direction, StrategyResult, clamp


def evaluate_volume(df: pd.DataFrame) -> StrategyResult:
    last = df.iloc[-1]
    reasons: list[str] = []
    long_score = 0.0
    short_score = 0.0

    close, vwap = last["close"], last["vwap"]
    volume_ratio = last["volume_ratio"]

    if pd.isna(vwap) or pd.isna(volume_ratio):
        return StrategyResult("거래량", 0.0, Direction.NEUTRAL, ["지표 데이터 부족"])

    # VWAP 대비 위치 (최대 40점)
    vwap_gap = (close - vwap) / vwap * 100
    if close > vwap:
        long_score += clamp(abs(vwap_gap) * 20 + 20, 0, 40)
        reasons.append(f"가격이 VWAP 위 ({vwap_gap:+.2f}%)")
    else:
        short_score += clamp(abs(vwap_gap) * 20 + 20, 0, 40)
        reasons.append(f"가격이 VWAP 아래 ({vwap_gap:+.2f}%)")

    # OBV 추세 (최대 30점) - 최근 10봉 기울기
    if len(df) > 10 and not df["obv"].iloc[-10:].isna().any():
        obv_slope = df["obv"].iloc[-1] - df["obv"].iloc[-10]
        if obv_slope > 0:
            long_score += 30
            reasons.append("OBV 상승 (매수세 유입)")
        elif obv_slope < 0:
            short_score += 30
            reasons.append("OBV 하락 (매도세 유입)")

    # 거래량 비율 (최대 30점) - 평균 대비 실린 거래량이 방향성 강화
    if volume_ratio >= 1.2:
        boost = clamp((volume_ratio - 1) * 30, 0, 30)
        if long_score >= short_score:
            long_score += boost
        else:
            short_score += boost
        reasons.append(f"거래량 평균 대비 {volume_ratio:.2f}배 (강한 참여)")
    else:
        reasons.append(f"거래량 평균 대비 {volume_ratio:.2f}배 (참여 저조)")

    if long_score > short_score:
        return StrategyResult("거래량", clamp(long_score), Direction.LONG, reasons)
    elif short_score > long_score:
        return StrategyResult("거래량", clamp(short_score), Direction.SHORT, reasons)
    return StrategyResult("거래량", clamp(max(long_score, short_score)), Direction.NEUTRAL, reasons)
