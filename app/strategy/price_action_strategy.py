"""④ 가격 행동 전략: 지지/저항, 돌파, 가짜돌파, Liquidity Sweep, Order Block, FVG"""
import pandas as pd

from app.strategy.base import Direction, StrategyResult, clamp

LOOKBACK = 30
PIVOT_WINDOW = 3


def get_support_resistance(df: pd.DataFrame) -> tuple[float, float]:
    """최근 구간의 저항(고점)/지지(저점) 레벨 (외부 모듈에서도 사용)"""
    window = df.iloc[-LOOKBACK:-1] if len(df) > LOOKBACK else df.iloc[:-1]
    resistance = window["high"].max()
    support = window["low"].min()
    return resistance, support


_find_levels = get_support_resistance  # 내부 호환용 별칭


def _detect_breakout_fakeout(df: pd.DataFrame, resistance: float, support: float) -> dict:
    last, prev = df.iloc[-1], df.iloc[-2]
    result = {"breakout": None, "fakeout": None}

    if prev["close"] <= resistance and last["close"] > resistance:
        result["breakout"] = "long"
    elif prev["close"] >= support and last["close"] < support:
        result["breakout"] = "short"

    # 가짜 돌파: 직전 1~3봉 내 돌파 후 레벨 안으로 재진입
    recent = df.iloc[-4:-1]
    if (recent["high"] > resistance).any() and last["close"] < resistance:
        result["fakeout"] = "long_trap"  # 상단 가짜돌파 -> 숏 관점
    if (recent["low"] < support).any() and last["close"] > support:
        result["fakeout"] = "short_trap"  # 하단 가짜돌파 -> 롱 관점
    return result


def _detect_liquidity_sweep(df: pd.DataFrame, resistance: float, support: float) -> str | None:
    last = df.iloc[-1]
    upper_wick = last["high"] - max(last["close"], last["open"])
    lower_wick = min(last["close"], last["open"]) - last["low"]
    body = abs(last["close"] - last["open"]) or 1e-9

    if last["high"] > resistance and last["close"] < resistance and upper_wick > body:
        return "short"  # 상단 유동성 쓸고 하락 반전
    if last["low"] < support and last["close"] > support and lower_wick > body:
        return "long"  # 하단 유동성 쓸고 상승 반전
    return None


def _detect_order_block(df: pd.DataFrame) -> str | None:
    """강한 임펄스 이전의 마지막 반대 캔들"""
    recent = df.iloc[-6:]
    if len(recent) < 4:
        return None
    impulse = recent["close"].iloc[-1] - recent["close"].iloc[-4]
    avg_range = (recent["high"] - recent["low"]).mean() or 1e-9

    if impulse > avg_range * 1.5:
        return "long"
    if impulse < -avg_range * 1.5:
        return "short"
    return None


def _detect_fvg(df: pd.DataFrame) -> str | None:
    """3봉 기준 Fair Value Gap"""
    if len(df) < 3:
        return None
    c1, c3 = df.iloc[-3], df.iloc[-1]
    if c3["low"] > c1["high"]:
        return "long"
    if c3["high"] < c1["low"]:
        return "short"
    return None


def evaluate_price_action(df: pd.DataFrame) -> StrategyResult:
    if len(df) < LOOKBACK:
        return StrategyResult("가격행동", 0.0, Direction.NEUTRAL, ["데이터 부족"])

    reasons: list[str] = []
    long_score = 0.0
    short_score = 0.0

    resistance, support = _find_levels(df)
    reasons.append(f"저항 {resistance:.3f} / 지지 {support:.3f}")

    bf = _detect_breakout_fakeout(df, resistance, support)
    if bf["breakout"] == "long":
        long_score += 25
        reasons.append("저항 상단 돌파")
    elif bf["breakout"] == "short":
        short_score += 25
        reasons.append("지지 하단 이탈")

    if bf["fakeout"] == "long_trap":
        short_score += 20
        reasons.append("상단 가짜 돌파 (숏 관점)")
    elif bf["fakeout"] == "short_trap":
        long_score += 20
        reasons.append("하단 가짜 돌파 (롱 관점)")

    sweep = _detect_liquidity_sweep(df, resistance, support)
    if sweep == "long":
        long_score += 25
        reasons.append("하단 Liquidity Sweep 후 반등")
    elif sweep == "short":
        short_score += 25
        reasons.append("상단 Liquidity Sweep 후 하락")

    ob = _detect_order_block(df)
    if ob == "long":
        long_score += 15
        reasons.append("Bullish Order Block 형성")
    elif ob == "short":
        short_score += 15
        reasons.append("Bearish Order Block 형성")

    fvg = _detect_fvg(df)
    if fvg == "long":
        long_score += 15
        reasons.append("상승 Fair Value Gap")
    elif fvg == "short":
        short_score += 15
        reasons.append("하락 Fair Value Gap")

    if long_score > short_score:
        return StrategyResult("가격행동", clamp(long_score), Direction.LONG, reasons)
    elif short_score > long_score:
        return StrategyResult("가격행동", clamp(short_score), Direction.SHORT, reasons)
    return StrategyResult("가격행동", clamp(max(long_score, short_score)), Direction.NEUTRAL, reasons)
