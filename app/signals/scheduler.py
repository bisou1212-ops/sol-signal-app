"""백그라운드 스케줄러: 대시보드를 아무도 안 보고 있어도 서버가 스스로 주기적으로
신호를 체크하고 기록한다. FastAPI startup 시점에 asyncio 백그라운드 태스크로 시작된다.

주의: Railway 서비스 자체가 죽거나 재시작되면(예: 무료/트라이얼 플랜 슬립, 배포 중 재시작)
이 태스크도 같이 중단된다. 서비스가 계속 떠 있는 동안에만 동작한다.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.data import signal_log
from app.signals.signal_generator import generate_signal
from app.signals.trade_resolver import resolve_pending_trades

logger = logging.getLogger("sol_signal_app.scheduler")

_task: asyncio.Task | None = None
_state = {
    "enabled": True,
    "running": False,
    "run_count": 0,
    "last_run_at": None,
    "last_status": None,   # "ok" | "error"
    "last_error": None,
    "last_position": None,  # 마지막으로 체크했을 때의 롱/숏/관망
}


async def _run_once() -> None:
    await resolve_pending_trades()
    result = await generate_signal()
    signal_log.log_signal(result)
    _state["last_position"] = result.position


async def _loop() -> None:
    _state["running"] = True
    logger.info("백그라운드 스케줄러 시작 (주기 %d초)", settings.scheduler_interval_seconds)
    while True:
        try:
            await _run_once()
            _state["last_status"] = "ok"
            _state["last_error"] = None
        except Exception as e:  # 한 번의 실패로 전체 루프가 죽지 않도록 반드시 잡아먹는다
            logger.exception("스케줄러 신호 체크 실패")
            _state["last_status"] = "error"
            _state["last_error"] = str(e)
        finally:
            _state["run_count"] += 1
            _state["last_run_at"] = datetime.now(timezone.utc).isoformat()

        await asyncio.sleep(settings.scheduler_interval_seconds)


def start() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
    _state["running"] = False


def get_status() -> dict:
    return {**_state, "interval_seconds": settings.scheduler_interval_seconds}
