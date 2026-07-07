"""5개 독립 전략 실행"""
import pandas as pd

from app.strategy.base import StrategyResult
from app.strategy.momentum_strategy import evaluate_momentum
from app.strategy.price_action_strategy import evaluate_price_action
from app.strategy.trend_strategy import evaluate_trend
from app.strategy.volatility_strategy import evaluate_volatility
from app.strategy.volume_strategy import evaluate_volume


def run_all_strategies(df: pd.DataFrame) -> list[StrategyResult]:
    """지표가 포함된 단일 시간봉 DataFrame으로 5개 전략을 모두 평가"""
    return [
        evaluate_trend(df),
        evaluate_momentum(df),
        evaluate_volume(df),
        evaluate_price_action(df),
        evaluate_volatility(df),
    ]
