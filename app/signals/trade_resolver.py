"""미종료(pending) 진입 신호의 승패를 실제 캔들로 판정한다.

백테스트(app/backtest/engine.py)의 SL/TP 판정 로직(TP 도달 시 손절가를 이전 레벨로
이동)과 동일한 규칙을 실시간 데이터에 적용한다. /signal 호출 시마다 자동 실행되어
쌓여있는 미종료 신호들을 검사하고, SL/TP 중 하나라도 닿았으면 승/패를 기록한다.
"""
import math
from datetime import datetime, timezone

import pandas as pd

from app.config import settings
from app.data import signal_log
from app.data.candle_store import fetch_candles_df

MAX_LOOKBACK_BARS = 2000  # 3분봉 2000개 = 약 4.2일. 이보다 오래된 미종료 신호는 다음 호출에도 재시도.


def _resolve_single(main_df: pd.DataFrame, trade: dict) -> tuple[str, float, float] | None:
    """entry_time 이후 캔들을 순회하며 SL/TP 도달 여부 판정. 아직 미도달이면 None."""
    entry_time = pd.Timestamp(trade["signal_time"])
    is_long = trade["position"] == "롱"
    entry, sl = trade["entry_price"], trade["stop_loss"]
    tp1, tp2, tp3 = trade["tp1"], trade["tp2"], trade["tp3"]
    if entry is None or sl is None:
        return None

    risk = abs(entry - sl)
    if risk == 0:
        return None

    bars_after_entry = main_df[main_df["timestamp"] > entry_time]
    if bars_after_entry.empty:
        return None  # 아직 진입 봉 이후 데이터 없음

    current_sl = sl
    hit_tp1 = hit_tp2 = False

    for _, bar in bars_after_entry.iterrows():
        low, high = bar["low"], bar["high"]

        stopped = (low <= current_sl) if is_long else (high >= current_sl)
        if stopped:
            exit_price = current_sl
            r = (exit_price - entry) / risk if is_long else (entry - exit_price) / risk
            outcome = "본전" if abs(exit_price - entry) < risk * 0.05 else ("익절" if r > 0 else "손절")
            return outcome, round(exit_price, 4), round(r, 2)

        if not hit_tp1 and tp1 and ((high >= tp1) if is_long else (low <= tp1)):
            hit_tp1, current_sl = True, entry
        if hit_tp1 and not hit_tp2 and tp2 and ((high >= tp2) if is_long else (low <= tp2)):
            hit_tp2, current_sl = True, tp1
        if hit_tp2 and tp3 and ((high >= tp3) if is_long else (low <= tp3)):
            r = (tp3 - entry) / risk if is_long else (entry - tp3) / risk
            return "익절", round(tp3, 4), round(r, 2)

    return None  # 아직 SL/TP 어느 쪽도 도달 안 함 (진행 중)


async def resolve_pending_trades(symbol: str = None) -> int:
    """미종료 신호들을 검사해 승패 확정. 확정된 건수를 반환."""
    pending = signal_log.get_pending_trades()
    if not pending:
        return 0

    oldest_time = min(pd.Timestamp(t["signal_time"]) for t in pending)
    elapsed_min = (datetime.now(timezone.utc) - oldest_time.to_pydatetime()).total_seconds() / 60
    bars_needed = min(MAX_LOOKBACK_BARS, math.ceil(elapsed_min / 3) + 20)

    main_df = await fetch_candles_df(settings.main_tf, symbol=symbol, limit=max(bars_needed, 50))
    if main_df.empty:
        return 0

    resolved_count = 0
    for trade in pending:
        result = _resolve_single(main_df, trade)
        if result is None:
            continue
        outcome, exit_price, r_multiple = result
        signal_log.update_trade_outcome(trade["id"], outcome, exit_price, r_multiple)
        resolved_count += 1

    return resolved_count
