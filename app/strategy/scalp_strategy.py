"""초단타 스켈핑 전략: 5개 조건 컨플루언스(Confluence) 방식

핵심 변경점 (v2): 방향 트리거(RSI 크로스) 이전이라도 "추세가 기울어진 쪽" 기준으로
5개 조건을 항상 채점해서 점수/기준/근거를 상시 표시한다. 단, 실제 진입 가능 여부
(composite.direction)는 기존과 동일하게 RSI(7) 실제 크로스가 일어난 경우에만 부여한다.
-> 화면에는 "지금 몇 점인지"가 항상 보이지만, 진입은 여전히 크로스 확정 시점에만 이뤄짐.

1. 추세필터   : 15분봉 EMA50 vs EMA200 (리닝 방향의 전제 조건, 항상 충족 상태로 표시)
2. VWAP      : 3분봉 가격이 VWAP 상/하단
3. 모멘텀전환 : RSI(7)가 40->50(롱) / 60->50(숏) 실제 크로스 여부 (미충족 시 현재 RSI 값 표시)
4. 거래량스파이크: 최근 거래량이 20봉 평균 대비 배수 이상
5. 구조유지   : 직전 스윙 저점/고점 붕괴 없음
"""
from dataclasses import dataclass, field

import pandas as pd
import ta

from app.config import settings
from app.strategy.base import Direction

CONDITION_NAMES = ["추세필터", "VWAP", "모멘텀전환", "거래량스파이크", "구조유지"]


@dataclass
class ScalpComposite:
    total_score: float
    direction: Direction           # 실제 진입 가능 방향 (RSI 크로스 확정 시에만 LONG/SHORT)
    agreement_count: int
    total_strategies: int
    breakdown: list[dict] = field(default_factory=list)
    lean: str = "neutral"          # 화면 표시용 리닝 방향 (추세 기준, 크로스 전이어도 표시)


def evaluate_scalp(main_df: pd.DataFrame, trend_df: pd.DataFrame) -> ScalpComposite:
    """main_df: 실행 타임프레임(지표 포함), trend_df: 추세 필터 타임프레임(지표 포함)"""
    if len(trend_df) < 210:
        need = 210 - len(trend_df)
        return ScalpComposite(0.0, Direction.NEUTRAL, 0, len(CONDITION_NAMES), [
            {"name": "추세필터", "score": 0, "direction": "neutral",
             "reasons": [f"15m 데이터 워밍업 중 (EMA200 계산에 {need}봉 더 필요)"]},
        ])
    if len(main_df) < settings.swing_lookback + 5:
        return ScalpComposite(0.0, Direction.NEUTRAL, 0, len(CONDITION_NAMES), [
            {"name": "구조유지", "score": 0, "direction": "neutral", "reasons": ["3m 데이터 워밍업 중"]},
        ])

    last = main_df.iloc[-1]
    rsi_series = ta.momentum.rsi(main_df["close"], window=settings.rsi_fast_period)
    rsi_now, rsi_prev = rsi_series.iloc[-1], rsi_series.iloc[-2]
    if pd.isna(rsi_now) or pd.isna(rsi_prev):
        return ScalpComposite(0.0, Direction.NEUTRAL, 0, len(CONDITION_NAMES), [
            {"name": "모멘텀전환", "score": 0, "direction": "neutral", "reasons": ["RSI 계산 데이터 부족"]},
        ])

    trend_last = trend_df.iloc[-1]
    uptrend = trend_last["ema50"] > trend_last["ema200"]
    downtrend = trend_last["ema50"] < trend_last["ema200"]

    # 리닝 방향: 추세 하나만으로 결정 (크로스 전이라도 "어느 쪽을 보고 있는지" 항상 표시)
    if uptrend:
        lean = Direction.LONG
    elif downtrend:
        lean = Direction.SHORT
    else:
        return ScalpComposite(0.0, Direction.NEUTRAL, 0, len(CONDITION_NAMES), [
            {"name": "추세필터", "score": 0, "direction": "neutral",
             "reasons": [f"15m EMA50({trend_last['ema50']:.3f})≈EMA200({trend_last['ema200']:.3f}) 방향 불명확"]},
        ])

    is_long = lean == Direction.LONG

    price, vwap = last["close"], last["vwap"]
    vwap_ok = (price > vwap) if is_long else (price < vwap)

    low_th, high_th = settings.rsi_entry_low, settings.rsi_entry_high
    rsi_crossed = (rsi_prev < low_th and rsi_now >= high_th) if is_long else (rsi_prev > (100 - low_th) and rsi_now <= (100 - high_th))

    vol_ratio = last["volume_ratio"]
    volume_spike = bool(pd.notna(vol_ratio) and vol_ratio >= settings.volume_multiplier)

    lb = settings.swing_lookback
    swing_low = main_df["low"].iloc[-(lb + 1):-1].min()
    swing_high = main_df["high"].iloc[-(lb + 1):-1].max()
    structure_ok = (price > swing_low) if is_long else (price < swing_high)

    # 근거 문자열 (충족/미충족 모두 기준값을 함께 표기)
    trend_reason = f"15m EMA50{'>' if is_long else '<'}EMA200 ({'상승' if is_long else '하락'} 추세, 리닝: {'롱' if is_long else '숏'})"

    if vwap_ok:
        vwap_reason = f"가격이 VWAP {'상단' if is_long else '하단'} 유지 (${price:.3f} vs ${vwap:.3f})"
    else:
        vwap_reason = f"가격이 VWAP {'하단' if is_long else '상단'} - 기준 미충족 (${price:.3f} vs ${vwap:.3f})"

    if rsi_crossed:
        momentum_reason = f"RSI(7) {rsi_prev:.1f}->{rsi_now:.1f} {'상향' if is_long else '하향'} 돌파 완료 (기준 {low_th if is_long else 100-low_th:.0f}->{high_th if is_long else 100-high_th:.0f})"
    else:
        target = f"{low_th:.0f} 이하 -> {high_th:.0f} 이상 상향" if is_long else f"{100-low_th:.0f} 이상 -> {100-high_th:.0f} 이하 하향"
        momentum_reason = f"RSI(7) 현재 {rsi_now:.1f} - 아직 크로스 전 (기준: {target} 돌파 필요)"

    if pd.isna(vol_ratio):
        volume_reason = "거래량 데이터 부족"
    elif volume_spike:
        volume_reason = f"거래량 {vol_ratio:.2f}배 (기준 {settings.volume_multiplier:.1f}배 이상 충족)"
    else:
        volume_reason = f"거래량 {vol_ratio:.2f}배 - 기준({settings.volume_multiplier:.1f}배) 미충족"

    if structure_ok:
        structure_reason = f"직전 스윙 {'저점' if is_long else '고점'} {'상회' if is_long else '하회'} 유지"
    else:
        structure_reason = f"직전 스윙 {'저점 붕괴' if is_long else '고점 돌파'} - 구조 깨짐"

    conditions = [
        ("추세필터", True, trend_reason),
        ("VWAP", vwap_ok, vwap_reason),
        ("모멘텀전환", rsi_crossed, momentum_reason),
        ("거래량스파이크", volume_spike, volume_reason),
        ("구조유지", structure_ok, structure_reason),
    ]

    met = sum(1 for _, ok, _ in conditions if ok)
    total_score = round(met / len(conditions) * 100, 1)
    breakdown = [
        {"name": name, "score": 100 if ok else 0,
         "direction": lean.value if ok else "neutral", "reasons": [reason]}
        for name, ok, reason in conditions
    ]

    # 실제 진입 가능 방향: RSI 실제 크로스가 확정된 경우만 (기존 안전장치 그대로 유지)
    trigger_direction = lean if rsi_crossed else Direction.NEUTRAL

    return ScalpComposite(total_score, trigger_direction, met, len(conditions), breakdown, lean=lean.value)
