"""백테스트 거래 결과 타입"""
from dataclasses import dataclass


@dataclass
class Trade:
    entry_time: str
    exit_time: str
    direction: str          # 롱 / 숏
    entry_price: float
    exit_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    r_multiple: float       # 손절폭(1R) 대비 손익 배수
    hit_tp1: bool
    hit_tp2: bool
    hit_tp3: bool
    outcome: str            # "익절", "손절", "본전", "미종료"
