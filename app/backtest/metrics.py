"""백테스트 결과 성과 지표 집계"""
from dataclasses import dataclass

from app.backtest.trade import Trade


@dataclass
class BacktestReport:
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_r: float
    avg_r: float
    profit_factor: float
    max_drawdown_r: float
    avg_win_r: float
    avg_loss_r: float


def summarize(trades: list[Trade]) -> BacktestReport:
    if not trades:
        return BacktestReport(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    wins = [t for t in trades if t.r_multiple > 0]
    losses = [t for t in trades if t.r_multiple <= 0]
    total_r = sum(t.r_multiple for t in trades)

    gross_profit = sum(t.r_multiple for t in wins)
    gross_loss = abs(sum(t.r_multiple for t in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")

    # 누적 R 기준 최대 낙폭
    cum, peak, max_dd = 0.0, 0.0, 0.0
    for t in trades:
        cum += t.r_multiple
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    return BacktestReport(
        total_trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=round(len(wins) / len(trades) * 100, 1),
        total_r=round(total_r, 2),
        avg_r=round(total_r / len(trades), 2),
        profit_factor=profit_factor,
        max_drawdown_r=round(max_dd, 2),
        avg_win_r=round(gross_profit / len(wins), 2) if wins else 0.0,
        avg_loss_r=round(gross_loss / len(losses), 2) if losses else 0.0,
    )
