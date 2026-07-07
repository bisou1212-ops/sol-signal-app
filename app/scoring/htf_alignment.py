"""상위 시간봉(1H, 4H) 추세 방향과 메인(15분) 신호 방향의 일치 여부 확인"""
import pandas as pd

from app.strategy.base import Direction
from app.strategy.trend_strategy import evaluate_trend


def check_htf_alignment(main_direction: Direction, htf1_df: pd.DataFrame, htf2_df: pd.DataFrame) -> dict:
    """1H, 4H 추세 전략 방향이 메인 방향과 일치하는지 확인"""
    htf1_trend = evaluate_trend(htf1_df)
    htf2_trend = evaluate_trend(htf2_df)

    htf1_match = htf1_trend.direction == main_direction and main_direction != Direction.NEUTRAL
    htf2_match = htf2_trend.direction == main_direction and main_direction != Direction.NEUTRAL

    return {
        "aligned": htf1_match and htf2_match,
        "htf1_direction": htf1_trend.direction.value,
        "htf2_direction": htf2_trend.direction.value,
        "htf1_match": htf1_match,
        "htf2_match": htf2_match,
    }
