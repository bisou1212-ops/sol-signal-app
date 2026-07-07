"""전략 모듈 공통 타입"""
from dataclasses import dataclass, field
from enum import Enum


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass
class StrategyResult:
    name: str
    score: float          # 0~100 (해당 전략의 강도)
    direction: Direction  # 이 전략이 가리키는 방향
    reasons: list[str] = field(default_factory=list)


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))
