"""FastAPI 진입점"""
import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.bitget_client import bitget_client
from app.backtest.data_loader import load_backtest_data
from app.backtest.engine import run_backtest, run_backtest_debug
from app.backtest.metrics import summarize
from app.config import settings
from app.data import signal_log
from app.signals.kelly_sizing import calculate_position
from app.signals.scheduler import get_status as scheduler_status_fn
from app.signals.scheduler import start as start_scheduler
from app.signals.scheduler import stop as stop_scheduler
from app.signals.signal_generator import generate_signal
from app.signals.trade_resolver import resolve_pending_trades

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sol_signal_app")

app = FastAPI(title="SOL 선물 매매 신호 앱")
signal_log.init_db()

DASHBOARD_HTML = (Path(__file__).parent / "ui" / "dashboard.html").read_text(encoding="utf-8")


@app.on_event("startup")
async def startup_event():
    start_scheduler()  # 대시보드를 아무도 안 봐도 서버가 알아서 주기적으로 신호 체크


@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()
    await bitget_client.close()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


@app.get("/health")
def health():
    return {"status": "ok", "symbol": settings.symbol}


@app.get("/scheduler/status")
def scheduler_status():
    """백그라운드 스케줄러가 정상 작동 중인지 확인 (run_count가 계속 늘어나야 정상)"""
    return scheduler_status_fn()


@app.get("/signal")
async def signal():
    try:
        await resolve_pending_trades()  # 이전 신호들 SL/TP 도달 여부 먼저 확인
        result = await generate_signal()
        signal_log.log_signal(result)
        return asdict(result)
    except Exception:
        logger.exception("신호 생성 실패")
        raise


@app.get("/signal/resolve")
async def signal_resolve():
    """미종료 신호 승패 판정을 수동으로 즉시 실행"""
    count = await resolve_pending_trades()
    return {"resolved": count}


@app.get("/signal/stats")
def signal_stats(hours: int = 24):
    return signal_log.get_stats(hours=hours)


@app.get("/signal/history")
def signal_history(limit: int = 50, trades_only: bool = False):
    return signal_log.get_recent(limit=limit, trades_only=trades_only)


@app.get("/backtest")
async def backtest(limit: int = 3000):
    tf_data = await load_backtest_data(limit=limit)
    trades = run_backtest(tf_data)
    report = summarize(trades)
    if report.total_trades > 0:
        signal_log.save_backtest_stats(
            win_rate=report.win_rate, avg_win_r=report.avg_win_r,
            avg_loss_r=report.avg_loss_r, total_trades=report.total_trades,
        )
    return {"report": asdict(report), "trades": [asdict(t) for t in trades]}


@app.get("/backtest/debug")
async def backtest_debug(limit: int = 5000):
    """왜 신호가 0건인지 단계별로 진단 (워밍업/크로스미발생/점수미달 구분)"""
    tf_data = await load_backtest_data(limit=limit)
    return run_backtest_debug(tf_data)


@app.get("/backtest/conditions")
async def backtest_conditions(limit: int = 3000):
    """조건별(추세필터/VWAP/모멘텀전환/거래량스파이크/구조유지) 승률 기여도 분석"""
    tf_data = await load_backtest_data(limit=limit)
    trades = run_backtest(tf_data)
    pairs = [(t.breakdown, t.r_multiple) for t in trades]
    return {"total_trades": len(trades), "conditions": signal_log.analyze_conditions(pairs)}


@app.get("/position/size")
def position_size(
    balance: float, entry_price: float, stop_price: float,
    win_rate: float | None = None, avg_win: float | None = None, avg_loss: float | None = None,
):
    """켈리 기준 포지션 사이징. win_rate/avg_win/avg_loss 미입력 시 최근 백테스트 실적 사용"""
    if win_rate is None or avg_win is None or avg_loss is None:
        stats = signal_log.get_backtest_stats()
        if not stats:
            return {"error": "백테스트 실적이 없습니다. /backtest를 먼저 실행하거나 win_rate/avg_win/avg_loss를 직접 입력하세요."}
        win_rate, avg_win, avg_loss = stats["win_rate"] / 100, stats["avg_win_r"], stats["avg_loss_r"]

    result = calculate_position(balance, entry_price, stop_price, win_rate, avg_win, avg_loss)
    if result is None:
        return {"error": "계산 불가 (잔고/진입가/손절폭 확인 필요)"}
    return asdict(result)
