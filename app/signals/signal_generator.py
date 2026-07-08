"""초단타 스켈핑: 5조건 컨플루언스 -> RR 검증 -> 켈리 사이징 -> 최종 신호"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from app.config import settings
from app.data import signal_log
from app.data.candle_store import fetch_multi_tf
from app.indicators.engine import compute_multi_tf
from app.signals.kelly_sizing import calculate_position
from app.signals.market_state import get_market_state, get_volatility_state
from app.signals.risk_manager import calculate_risk_targets
from app.strategy.base import Direction
from app.strategy.scalp_strategy import evaluate_scalp

POSITION_LABEL = {Direction.LONG: "롱", Direction.SHORT: "숏", Direction.NEUTRAL: "관망"}

# 백테스트 실적이 아직 없을 때 켈리 계산에 쓰는 보수적 기본 가정치
DEFAULT_WIN_RATE = 0.5
DEFAULT_AVG_WIN_R = 1.5
DEFAULT_AVG_LOSS_R = 1.0


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
    # 켈리 사이징 (is_trade=True일 때만 값 존재)
    suggested_risk_pct: float | None = None
    suggested_leverage: int | None = None
    suggested_position_size: float | None = None
    sizing_note: str = ""


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
    """지표가 포함된 멀티 타임프레임 데이터로 최종 신호 생성 (main=3m 실행봉, htf1=15m 추세필터)"""
    main_df = tf_data["main"]
    trend_df = tf_data["htf1"]
    current_price = float(main_df.iloc[-1]["close"])

    composite = evaluate_scalp(main_df, trend_df)

    market_state = get_market_state(trend_df, composite.direction)
    volatility_state = get_volatility_state(main_df)

    if composite.direction == Direction.NEUTRAL:
        return _build_no_trade(current_price, composite, market_state, volatility_state, "5조건 컨플루언스 미충족 (방향성 불명확)")

    if composite.total_score < settings.min_score:
        return _build_no_trade(
            current_price, composite, market_state, volatility_state,
            f"조건 충족 {composite.agreement_count}/{composite.total_strategies} ({composite.total_score:.0f}점) < 기준 {settings.min_score}점",
        )

    risk = calculate_risk_targets(main_df, composite.direction)
    if risk is None or risk.risk_reward < settings.min_risk_reward:
        rr_val = risk.risk_reward if risk else 0
        return _build_no_trade(
            current_price, composite, market_state, volatility_state,
            f"손익비 {rr_val} < 기준 1:{settings.min_risk_reward}",
        )

    reasons = [f"{b['name']}: {b['reasons'][0]}" for b in composite.breakdown]

    # 켈리 사이징: 최근 백테스트 실적이 있으면 사용, 없으면 보수적 기본값
    stats = signal_log.get_backtest_stats()
    if stats:
        win_rate, avg_win, avg_loss = stats["win_rate"] / 100, stats["avg_win_r"], stats["avg_loss_r"]
        sizing_note = f"백테스트 실적 기반 (표본 {stats['total_trades']}건, {stats['updated_at'][:10]} 기준)"
    else:
        win_rate, avg_win, avg_loss = DEFAULT_WIN_RATE, DEFAULT_AVG_WIN_R, DEFAULT_AVG_LOSS_R
        sizing_note = "백테스트 실적 없음 - 보수적 기본 가정치(승률50%/RR1.5) 사용. /backtest 먼저 실행 권장"

    sizing = calculate_position(
        balance=1_000_000,  # 계좌 잔고는 % 기준으로만 쓰이므로 임의 기준값(비율 계산용)
        entry_price=risk.entry, stop_price=risk.stop_loss,
        win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss,
    )
    if sizing and sizing.note:
        sizing_note = sizing.note

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
        suggested_risk_pct=sizing.risk_pct if sizing else None,
        suggested_leverage=sizing.suggested_leverage if sizing else None,
        suggested_position_size=sizing.position_size if sizing else None,
        sizing_note=sizing_note,
    )


async def generate_signal(symbol: str = None) -> Signal:
    """실시간 데이터 수집 -> 지표 계산 -> 신호 생성 전체 파이프라인"""
    raw = await fetch_multi_tf(symbol=symbol)
    tf_data = compute_multi_tf(raw)
    return build_signal(tf_data)
