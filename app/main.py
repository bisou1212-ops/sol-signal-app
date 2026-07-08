"""FastAPI 진입점"""
import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.bitget_client import bitget_client
from app.backtest.data_loader import load_backtest_data
from app.backtest.engine import run_backtest
from app.backtest.metrics import summarize
from app.config import settings
from app.data import signal_log
from app.signals.signal_generator import generate_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sol_signal_app")

app = FastAPI(title="SOL 선물 매매 신호 앱")
signal_log.init_db()

DASHBOARD_HTML = (Path(__file__).parent / "ui" / "dashboard.html").read_text(encoding="utf-8")


@app.on_event("shutdown")
async def shutdown_event():
    await bitget_client.close()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


@app.get("/health")
def health():
    return {"status": "ok", "symbol": settings.symbol}


@app.get("/signal")
async def signal():
    try:
        result = await generate_signal()
        signal_log.log_signal(result)
        return asdict(result)
    except Exception:
        logger.exception("신호 생성 실패")
        raise


@app.get("/signal/stats")
def signal_stats(hours: int = 24):
    return signal_log.get_stats(hours=hours)


@app.get("/signal/history")
def signal_history(limit: int = 50, trades_only: bool = False):
    return signal_log.get_recent(limit=limit, trades_only=trades_only)


@app.get("/backtest")
async def backtest(limit: int = 1000):
    tf_data = await load_backtest_data(limit=limit)
    trades = run_backtest(tf_data)
    report = summarize(trades)
    return {"report": asdict(report), "trades": [asdict(t) for t in trades]}
