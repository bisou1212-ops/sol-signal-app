"""켈리 기준(하프 켈리) 포지션 사이징

승률/평균손익(R배수) 입력을 받아 리스크 비율, 진입 수량, 권장 레버리지를 계산한다.
승률/평균손익은 /backtest 실행 결과(app/data/signal_log.py의 backtest_cache)에서
가져오거나, 호출 시 직접 값을 넘길 수 있다.
"""
from dataclasses import dataclass

from app.config import settings


@dataclass
class PositionSizing:
    risk_pct: float
    risk_amount: float
    position_size: float
    suggested_leverage: int
    stop_distance_pct: float
    kelly_raw: float
    note: str


def kelly_fraction_raw(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """f* = W - (1-W)/B  (B = 평균이익/평균손실)"""
    if avg_loss <= 0 or win_rate <= 0:
        return 0.0
    b = avg_win / avg_loss
    if b <= 0:
        return 0.0
    kelly = win_rate - (1 - win_rate) / b
    return max(0.0, kelly)


def calculate_position(
    balance: float,
    entry_price: float,
    stop_price: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> PositionSizing | None:
    if balance <= 0 or entry_price <= 0:
        return None

    stop_distance = abs(entry_price - stop_price)
    if stop_distance == 0:
        return None

    kelly_raw = kelly_fraction_raw(win_rate, avg_win, avg_loss)
    risk_pct = min(kelly_raw * settings.kelly_fraction, settings.max_risk_per_trade)

    note = ""
    if kelly_raw == 0.0:
        note = "켈리 결과 0 이하(기대값 마이너스) - 최소 리스크만 사용 권장"
        risk_pct = 0.0

    risk_amount = balance * risk_pct
    position_size = risk_amount / stop_distance if risk_pct > 0 else 0.0

    required_margin = position_size * entry_price
    max_margin_use = balance * settings.margin_use_ratio
    implied_leverage = (required_margin / max_margin_use) if max_margin_use > 0 and required_margin > 0 else 1
    leverage = max(1, min(round(implied_leverage), settings.max_leverage))

    return PositionSizing(
        risk_pct=round(risk_pct * 100, 2),
        risk_amount=round(risk_amount, 2),
        position_size=round(position_size, 4),
        suggested_leverage=leverage,
        stop_distance_pct=round(stop_distance / entry_price * 100, 2),
        kelly_raw=round(kelly_raw, 4),
        note=note,
    )
