"""워크포워드 방식 백테스트: 룩어헤드 없이 과거 각 시점에서 신호 생성 후 결과 추적"""
import pandas as pd

from app.backtest.trade import Trade
from app.config import settings
from app.signals.signal_generator import build_signal
from app.strategy.base import Direction
from app.strategy.scalp_strategy import evaluate_scalp

MIN_WARMUP_BARS = 30  # 메인(3m)은 RSI7/거래량평균/스윙 계산에 필요한 최소치만. EMA200 워밍업은 15m 추세필터 df 자체에서 처리.


def _htf_slice(htf_df: pd.DataFrame, cutoff_time: pd.Timestamp) -> pd.DataFrame:
    """메인 봉 시각 기준으로 이미 '마감된' 상위 시간봉만 사용 (미래 데이터 누출 방지)"""
    return htf_df[htf_df["timestamp"] <= cutoff_time]


def _simulate_trade(main_df: pd.DataFrame, start_idx: int, direction: str,
                     entry: float, sl: float, tp1: float, tp2: float, tp3: float,
                     breakdown: list[dict]) -> tuple[Trade, int]:
    """진입 이후 봉을 순회하며 SL/TP 도달 여부 판정 (TP 도달 시 손절가를 이전 레벨로 이동)"""
    is_long = direction == "롱"
    risk = abs(entry - sl)
    current_sl = sl
    hit_tp1 = hit_tp2 = hit_tp3 = False

    for j in range(start_idx + 1, len(main_df)):
        bar = main_df.iloc[j]
        low, high = bar["low"], bar["high"]

        # 손절 체크 (이동된 손절가 기준)
        stopped = (low <= current_sl) if is_long else (high >= current_sl)
        if stopped:
            exit_price = current_sl
            r = (exit_price - entry) / risk if is_long else (entry - exit_price) / risk
            outcome = "본전" if abs(exit_price - entry) < risk * 0.05 else ("익절" if r > 0 else "손절")
            trade = Trade(
                entry_time=str(main_df.iloc[start_idx]["timestamp"]),
                exit_time=str(bar["timestamp"]),
                direction=direction, entry_price=entry, exit_price=exit_price,
                stop_loss=sl, tp1=tp1, tp2=tp2, tp3=tp3,
                r_multiple=round(r, 2), hit_tp1=hit_tp1, hit_tp2=hit_tp2, hit_tp3=hit_tp3,
                outcome=outcome, breakdown=breakdown,
            )
            return trade, j

        # TP 도달 체크 (순서대로) + 손절가 상향/하향 이동 (물타기 없이 이익 보호)
        if not hit_tp1 and ((high >= tp1) if is_long else (low <= tp1)):
            hit_tp1, current_sl = True, entry
        if hit_tp1 and not hit_tp2 and ((high >= tp2) if is_long else (low <= tp2)):
            hit_tp2, current_sl = True, tp1
        if hit_tp2 and not hit_tp3 and ((high >= tp3) if is_long else (low <= tp3)):
            hit_tp3 = True
            r = (tp3 - entry) / risk if is_long else (entry - tp3) / risk
            trade = Trade(
                entry_time=str(main_df.iloc[start_idx]["timestamp"]),
                exit_time=str(bar["timestamp"]),
                direction=direction, entry_price=entry, exit_price=tp3,
                stop_loss=sl, tp1=tp1, tp2=tp2, tp3=tp3,
                r_multiple=round(r, 2), hit_tp1=True, hit_tp2=True, hit_tp3=True,
                outcome="익절", breakdown=breakdown,
            )
            return trade, j

    # 데이터 끝까지 미종료
    last_bar = main_df.iloc[-1]
    exit_price = last_bar["close"]
    r = (exit_price - entry) / risk if is_long else (entry - exit_price) / risk
    trade = Trade(
        entry_time=str(main_df.iloc[start_idx]["timestamp"]),
        exit_time=str(last_bar["timestamp"]),
        direction=direction, entry_price=entry, exit_price=exit_price,
        stop_loss=sl, tp1=tp1, tp2=tp2, tp3=tp3,
        r_multiple=round(r, 2), hit_tp1=hit_tp1, hit_tp2=hit_tp2, hit_tp3=hit_tp3,
        outcome="미종료", breakdown=breakdown,
    )
    return trade, len(main_df) - 1


def run_backtest(tf_data: dict[str, pd.DataFrame]) -> list[Trade]:
    """전체 히스토리를 워크포워드로 순회하며 조건 충족 시 거래 시뮬레이션"""
    main_df = tf_data["main"]
    htf1_df, htf2_df = tf_data["htf1"], tf_data["htf2"]
    trades: list[Trade] = []

    i = MIN_WARMUP_BARS
    while i < len(main_df) - 1:
        window_main = main_df.iloc[: i + 1]
        cutoff = window_main.iloc[-1]["timestamp"]
        window_htf1 = _htf_slice(htf1_df, cutoff)
        window_htf2 = _htf_slice(htf2_df, cutoff)

        if len(window_htf1) < 20 or len(window_htf2) < 20:
            i += 1
            continue

        signal = build_signal({"main": window_main, "htf1": window_htf1, "htf2": window_htf2})

        if signal.is_trade:
            trade, exit_idx = _simulate_trade(
                main_df, i, signal.position,
                signal.entry_price, signal.stop_loss, signal.tp1, signal.tp2, signal.tp3,
                signal.strategy_breakdown,
            )
            trades.append(trade)
            i = exit_idx + 1  # 포지션 종료 후에만 다음 신호 탐색 (물타기/중복 진입 금지)
        else:
            i += 1

    return trades


def run_backtest_debug(tf_data: dict[str, pd.DataFrame]) -> dict:
    """어느 단계에서 신호가 막히는지 진단 (워밍업 부족 / 크로스 미발생 / 점수 미달 등을 구분)"""
    main_df = tf_data["main"]
    htf1_df, htf2_df = tf_data["htf1"], tf_data["htf2"]

    counters = {
        "total_bars_walked": 0,
        "skipped_htf_too_short": 0,
        "warmup_trend": 0,
        "warmup_main": 0,
        "rsi_na": 0,
        "flat_trend": 0,
        "cross_not_fired": 0,       # 방향은 있는데(리닝) 아직 RSI 크로스 자체가 안 남
        "crossed_but_low_score": 0,  # 크로스는 났는데 총점이 min_score 미달
        "trade_signals": 0,
    }
    score_when_crossed: list[float] = []

    i = MIN_WARMUP_BARS
    while i < len(main_df) - 1:
        counters["total_bars_walked"] += 1
        window_main = main_df.iloc[: i + 1]
        cutoff = window_main.iloc[-1]["timestamp"]
        window_htf1 = _htf_slice(htf1_df, cutoff)
        window_htf2 = _htf_slice(htf2_df, cutoff)

        if len(window_htf1) < 20 or len(window_htf2) < 20:
            counters["skipped_htf_too_short"] += 1
            i += 1
            continue

        composite = evaluate_scalp(window_main, window_htf1)

        if composite.status in ("warmup_trend", "warmup_main", "rsi_na", "flat_trend"):
            counters[composite.status] += 1
        elif composite.direction == Direction.NEUTRAL:
            counters["cross_not_fired"] += 1
        else:
            score_when_crossed.append(composite.total_score)
            if composite.total_score < settings.min_score:
                counters["crossed_but_low_score"] += 1
            else:
                counters["trade_signals"] += 1

        i += 1

    return {
        "main_bars": len(main_df),
        "trend_bars": len(htf1_df),
        "main_range": [str(main_df.iloc[0]["timestamp"]), str(main_df.iloc[-1]["timestamp"])] if len(main_df) else None,
        "trend_range": [str(htf1_df.iloc[0]["timestamp"]), str(htf1_df.iloc[-1]["timestamp"])] if len(htf1_df) else None,
        "counters": counters,
        "cross_fired_count": len(score_when_crossed),
        "avg_score_when_crossed": round(sum(score_when_crossed) / len(score_when_crossed), 1) if score_when_crossed else None,
    }
