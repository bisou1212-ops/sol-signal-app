"""5개 전략 -> 점수 종합 -> 상위시간봉 일치 -> RR 검증 -> 최종 신호"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from app.config import settings
from app.data.candle_store import fetch_multi_tf
from app.indicators.engine import compute_multi_tf
from app.scoring.htf_alignment import check_htf_alignment
from app.scoring.score_engine import calculate_composite_score
from app.signals.market_state import get_market_state, get_volatility_state
from app.signals.risk_manager import calculate_risk_targets
from app.strategy.base import Direction
from app.strategy.engine import run_all_strategies

POSITION_LABEL = {Direction.LONG: "롱", Direction.SHORT: "숏", Direction.NEUTRAL: "관망"}


@dataclass
class Signal:
    current_price: float
    position: str                  # 롱 / 숏 / 관망
    confidence: float              # %
    entry_price: float | None
    stop_loss: float | None
    tp1: float | None
    tp2: float | None
    tp3: float | None
    risk_reward: float | None
    market_state: str
    volatility_state: str
    signal_time: str
    is_trade: bool
    reasons: list[str] = field(default_factory=list)
    strategy_breakdown: list[dict] = field(default_factory=list)
    htf_info: dict = field(default_factory=dict)


def _build_no_trade(
    current_price: float,
    composite,
    market_state: str,
    volatility_state: str,
    extra_reason: str,
) -> Signal:
    return Signal(
        current_price=round(current_price, 4),
        position="관망",
        confidence=composite.total_score,
        entry_price=None,
        stop_loss=None,
        tp1=None,
        tp2=None,
        tp3=None,
        risk_reward=None,
        market_state=market_state,
        volatility_state=volatility_state,
        signal_time=datetime.now(timezone.utc).isoformat(),
        is_trade=False,
        reasons=[extra_reason],
        strategy_breakdown=composite.breakdown,
    )


def build_signal(tf_data: dict[str, pd.DataFrame]) -> Signal:
    """지표가 포함된 멀티 타임프레임 데이터로 최종 신호 생성"""
    main_df = tf_data["main"]
    current_price = float(main_df.iloc[-1]["close"])

    results = run_all_strategies(main_df)
    composite = calculate_composite_score(results)

    market_state = get_market_state(main_df, composite.direction)
    volatility_state = get_volatility_state(main_df)

    if composite.direction == Direction.NEUTRAL:
        return _build_no_trade(current_price, composite, market_state, volatility_state, "방향성 불명확")

    if composite.total_score < settings.min_score:
        return _build_no_trade(
            current_price, composite, market_state, volatility_state,
            f"종합 점수 {composite.total_score:.1f} < 기준 {settings.min_score}",
        )

    htf_check = check_htf_alignment(composite.direction, tf_data["htf1"], tf_data["htf2"])
    if not htf_check["aligned"]:
        signal = _build_no_trade(
            current_price, composite, market_state, volatility_state,
            f"상위 시간봉 불일치 (1H:{htf_check['htf1_direction']}, 4H:{htf_check['htf2_direction']})",
        )
        signal.htf_info = htf_check
        return signal

    risk = calculate_risk_targets(main_df, composite.direction)
    if risk is None or risk.risk_reward < settings.min_risk_reward:
        rr_val = risk.risk_reward if risk else 0
        signal = _build_no_trade(
            current_price, composite, market_state, volatility_state,
            f"손익비 {rr_val} < 기준 1:{settings.min_risk_reward}",
        )
        signal.htf_info = htf_check
        return signal

    reasons = [f"{b['name']} {b['score']}점: {', '.join(b['reasons'][:2])}" for b in composite.breakdown]

    return Signal(
        current_price=round(current_price, 4),
        position=POSITION_LABEL[composite.direction],
        confidence=composite.total_score,
        entry_price=risk.entry,
        stop_loss=risk.stop_loss,
        tp1=risk.tp1,
        tp2=risk.tp2,
        tp3=risk.tp3,
        risk_reward=risk.risk_reward,
        market_state=market_state,
        volatility_state=volatility_state,
        signal_time=datetime.now(timezone.utc).isoformat(),
        is_trade=True,
        reasons=reasons,
        strategy_breakdown=composite.breakdown,
        htf_info=htf_check,
    )


async def generate_signal(symbol: str = None) -> Signal:
    """실시간 데이터 수집 -> 지표 계산 -> 신호 생성 전체 파이프라인"""
    raw = await fetch_multi_tf(symbol=symbol)
    tf_data = compute_multi_tf(raw)
    return build_signal(tf_data)
