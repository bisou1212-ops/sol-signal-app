"""5개 전략 점수를 가중 종합하여 최종 스코어 산출"""
from dataclasses import dataclass, field

from app.strategy.base import Direction, StrategyResult

# 전략별 가중치 (합계 1.0)
STRATEGY_WEIGHTS: dict[str, float] = {
    "추세": 0.25,
    "모멘텀": 0.20,
    "거래량": 0.20,
    "가격행동": 0.20,
    "변동성": 0.15,
}

CONFLICT_PENALTY = 0.5  # 반대 방향 전략 점수 반영 비율(감점 강도)


@dataclass
class CompositeScore:
    total_score: float                 # 0~100 최종 종합 점수
    direction: Direction                # 최종 판단 방향
    agreement_count: int                # 방향 일치 전략 수 (0~5)
    total_strategies: int
    breakdown: list[dict] = field(default_factory=list)


def calculate_composite_score(results: list[StrategyResult]) -> CompositeScore:
    long_weighted = 0.0
    short_weighted = 0.0
    breakdown: list[dict] = []

    for r in results:
        weight = STRATEGY_WEIGHTS.get(r.name, 1.0 / len(results))
        if r.direction == Direction.LONG:
            long_weighted += r.score * weight
        elif r.direction == Direction.SHORT:
            short_weighted += r.score * weight
        breakdown.append(
            {"name": r.name, "score": round(r.score, 1), "direction": r.direction.value, "reasons": r.reasons}
        )

    if long_weighted == 0 and short_weighted == 0:
        return CompositeScore(0.0, Direction.NEUTRAL, 0, len(results), breakdown)

    if long_weighted >= short_weighted:
        majority = Direction.LONG
        align, conflict = long_weighted, short_weighted
    else:
        majority = Direction.SHORT
        align, conflict = short_weighted, long_weighted

    total_score = max(0.0, min(100.0, align - conflict * CONFLICT_PENALTY))
    agreement_count = sum(1 for r in results if r.direction == majority)

    return CompositeScore(
        total_score=round(total_score, 1),
        direction=majority,
        agreement_count=agreement_count,
        total_strategies=len(results),
        breakdown=breakdown,
    )
