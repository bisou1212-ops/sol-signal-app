"""초단타 스켈핑 전략: 5개 조건 컨플루언스(Confluence) 방식

실행 타임프레임(main, 기본 3분봉)과 단일 추세 필터(trend, 기본 15분봉)를 받아
아래 5개 조건을 평가한다. 조건은 각 1점(가중치 동일)이며, 충족 개수/5 * 100 이
종합 점수가 된다 (기존 5전략 스코어링 시스템과 인터페이스 호환을 위함).

1. 추세필터   : 15분봉 EMA50 vs EMA200
2. VWAP      : 3분봉 가격이 VWAP 상/하단
3. 모멘텀전환 : RSI(7)가 40->50(롱) / 60->50(숏) 크로스
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
    direction: Direction
    agreement_count: int
    total_strategies: int
    breakdown: list[dict] = field(default_factory=list)


def evaluate_scalp(main_df: pd.DataFrame, trend_df: pd.DataFrame) -> ScalpComposite:
    """main_df: 실행 타임프레임(지표 포함), trend_df: 추세 필터 타임프레임(지표 포함)"""
    if len(main_df) < settings.swing_lookback + 5 or len(trend_df) < 210:
        return ScalpComposite(0.0, Direction.NEUTRAL, 0, len(CONDITION_NAMES), [])

    last = main_df.iloc[-1]
    rsi_series = ta.momentum.rsi(main_df["close"], window=settings.rsi_fast_period)
    rsi_now, rsi_prev = rsi_series.iloc[-1], rsi_series.iloc[-2]
    if pd.isna(rsi_now) or pd.isna(rsi_prev):
        return ScalpComposite(0.0, Direction.NEUTRAL, 0, len(CONDITION_NAMES), [])

    trend_last = trend_df.iloc[-1]
    uptrend = trend_last["ema50"] > trend_last["ema200"]
    downtrend = trend_last["ema50"] < trend_last["ema200"]

    price, vwap = last["close"], last["vwap"]
    vwap_long, vwap_short = (price > vwap), (price < vwap)

    low_th, high_th = settings.rsi_entry_low, settings.rsi_entry_high
    rsi_up = rsi_prev < low_th and rsi_now >= high_th
    rsi_down = rsi_prev > (100 - low_th) and rsi_now <= (100 - high_th)

    vol_ratio = last["volume_ratio"]
    volume_spike = bool(pd.notna(vol_ratio) and vol_ratio >= settings.volume_multiplier)

    lb = settings.swing_lookback
    swing_low = main_df["low"].iloc[-(lb + 1):-1].min()
    swing_high = main_df["high"].iloc[-(lb + 1):-1].max()
    structure_long = price > swing_low
    structure_short = price < swing_high

    # 방향 결정: 추세 + 모멘텀 전환이 핵심(core) 조건, 나머지는 점수 가산용
    if uptrend and rsi_up:
        direction = Direction.LONG
    elif downtrend and rsi_down:
        direction = Direction.SHORT
    else:
        return ScalpComposite(0.0, Direction.NEUTRAL, 0, len(CONDITION_NAMES), [
            {"name": "추세필터", "score": 100 if (uptrend or downtrend) else 0,
             "direction": "long" if uptrend else "short" if downtrend else "neutral",
             "reasons": ["15m EMA50>EMA200 (상승)" if uptrend else "15m EMA50<EMA200 (하락)" if downtrend else "추세 불명확"]},
            {"name": "모멘텀전환", "score": 0, "direction": "neutral",
             "reasons": [f"RSI(7) {rsi_prev:.1f}->{rsi_now:.1f} (전환 신호 없음)"]},
        ])

    is_long = direction == Direction.LONG
    conditions = [
        ("추세필터", uptrend if is_long else downtrend,
         f"15m EMA50{'>' if is_long else '<'}EMA200 ({'상승' if is_long else '하락'})"),
        ("VWAP", vwap_long if is_long else vwap_short,
         f"가격이 VWAP {'상단' if is_long else '하단'} (${price:.3f} vs ${vwap:.3f})"),
        ("모멘텀전환", rsi_up if is_long else rsi_down,
         f"RSI(7) {rsi_prev:.1f}->{rsi_now:.1f} {'상향' if is_long else '하향'} 돌파"),
        ("거래량스파이크", volume_spike,
         f"거래량 {vol_ratio:.2f}배" if pd.notna(vol_ratio) else "거래량 데이터 부족"),
        ("구조유지", structure_long if is_long else structure_short,
         f"직전 스윙 {'저점' if is_long else '고점'} {'상회' if is_long else '하회'} 유지"),
    ]

    met = sum(1 for _, ok, _ in conditions if ok)
    total_score = round(met / len(conditions) * 100, 1)
    breakdown = [
        {"name": name, "score": 100 if ok else 0,
         "direction": direction.value if ok else "neutral", "reasons": [reason]}
        for name, ok, reason in conditions
    ]

    return ScalpComposite(total_score, direction, met, len(conditions), breakdown)
