"""ATR + 구조적 레벨 기반 손절/익절 계산"""
from dataclasses import dataclass

import pandas as pd

from app.config import settings
from app.strategy.base import Direction
from app.strategy.price_action_strategy import get_support_resistance

ATR_SL_MULT = 1.5


@dataclass
class RiskTargets:
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_reward: float


def calculate_risk_targets(df: pd.DataFrame, direction: Direction) -> RiskTargets | None:
    if direction == Direction.NEUTRAL:
        return None

    last = df.iloc[-1]
    entry = float(last["close"])
    atr = float(last["atr"])
    if atr <= 0:
        return None

    resistance, support = get_support_resistance(df)
    min_rr = settings.min_risk_reward

    if direction == Direction.LONG:
        stop_loss = entry - atr * ATR_SL_MULT
        risk = entry - stop_loss
        # 구조적 저항을 1차 목표로, 최소 RR 미달 시 배수로 확장
        tp2 = resistance if resistance > entry + risk * min_rr else entry + risk * min_rr
        tp1 = entry + (tp2 - entry) * 0.5
        tp3 = entry + (tp2 - entry) * 1.6
        rr = (tp2 - entry) / risk
    else:
        stop_loss = entry + atr * ATR_SL_MULT
        risk = stop_loss - entry
        tp2 = support if support < entry - risk * min_rr else entry - risk * min_rr
        tp1 = entry - (entry - tp2) * 0.5
        tp3 = entry - (entry - tp2) * 1.6
        rr = (entry - tp2) / risk

    return RiskTargets(
        entry=round(entry, 4),
        stop_loss=round(stop_loss, 4),
        tp1=round(tp1, 4),
        tp2=round(tp2, 4),
        tp3=round(tp3, 4),
        risk_reward=round(rr, 2),
    )
