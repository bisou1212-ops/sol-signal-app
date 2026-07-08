"""신호 이력 저장 및 통계 (SQLite)"""
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "signal_history.db"


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS signal_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_time TEXT NOT NULL,
                is_trade INTEGER NOT NULL,
                position TEXT NOT NULL,
                confidence REAL NOT NULL,
                current_price REAL NOT NULL,
                entry_price REAL,
                stop_loss REAL,
                risk_reward REAL,
                no_trade_reason TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS backtest_cache (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                win_rate REAL NOT NULL,
                avg_win_r REAL NOT NULL,
                avg_loss_r REAL NOT NULL,
                total_trades INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def log_signal(signal) -> None:
    d = asdict(signal)
    with _conn() as c:
        c.execute(
            """INSERT INTO signal_log
               (signal_time, is_trade, position, confidence, current_price,
                entry_price, stop_loss, risk_reward, no_trade_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d["signal_time"], int(d["is_trade"]), d["position"], d["confidence"],
                d["current_price"], d["entry_price"], d["stop_loss"], d["risk_reward"],
                None if d["is_trade"] else (d["reasons"][0] if d["reasons"] else None),
            ),
        )


def get_stats(hours: int = 24) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) n FROM signal_log WHERE signal_time >= ?", (since,)).fetchone()["n"]
        trades = c.execute(
            "SELECT COUNT(*) n FROM signal_log WHERE signal_time >= ? AND is_trade = 1", (since,)
        ).fetchone()["n"]
        by_position = c.execute(
            "SELECT position, COUNT(*) n FROM signal_log WHERE signal_time >= ? AND is_trade = 1 GROUP BY position",
            (since,),
        ).fetchall()
        top_no_trade = c.execute(
            """SELECT no_trade_reason, COUNT(*) n FROM signal_log
               WHERE signal_time >= ? AND is_trade = 0 AND no_trade_reason IS NOT NULL
               GROUP BY no_trade_reason ORDER BY n DESC LIMIT 5""",
            (since,),
        ).fetchall()
        avg_conf = c.execute(
            "SELECT AVG(confidence) a FROM signal_log WHERE signal_time >= ?", (since,)
        ).fetchone()["a"]

    return {
        "period_hours": hours,
        "total_checks": total,
        "trade_signals": trades,
        "no_trade_count": total - trades,
        "trade_rate_pct": round(trades / total * 100, 2) if total else 0.0,
        "by_position": {r["position"]: r["n"] for r in by_position},
        "top_no_trade_reasons": [{"reason": r["no_trade_reason"], "count": r["n"]} for r in top_no_trade],
        "avg_confidence": round(avg_conf, 1) if avg_conf else 0.0,
    }


def get_recent(limit: int = 50, trades_only: bool = False) -> list[dict]:
    query = "SELECT * FROM signal_log"
    if trades_only:
        query += " WHERE is_trade = 1"
    query += " ORDER BY id DESC LIMIT ?"
    with _conn() as c:
        rows = c.execute(query, (limit,)).fetchall()
    return [dict(r) for r in rows]


def save_backtest_stats(win_rate: float, avg_win_r: float, avg_loss_r: float, total_trades: int) -> None:
    """/backtest 실행 결과를 저장 -> 켈리 사이징이 최신 실적을 참조하도록 캐시"""
    with _conn() as c:
        c.execute(
            """INSERT INTO backtest_cache (id, win_rate, avg_win_r, avg_loss_r, total_trades, updated_at)
               VALUES (1, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 win_rate=excluded.win_rate, avg_win_r=excluded.avg_win_r,
                 avg_loss_r=excluded.avg_loss_r, total_trades=excluded.total_trades,
                 updated_at=excluded.updated_at""",
            (win_rate, avg_win_r, avg_loss_r, total_trades, datetime.now(timezone.utc).isoformat()),
        )


def get_backtest_stats() -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM backtest_cache WHERE id = 1").fetchone()
    if not row or row["total_trades"] < 10:  # 표본 너무 적으면 신뢰 불가 -> 기본값 사용하도록 None 반환
        return None
    return dict(row)


def analyze_conditions(trades_breakdown: list[tuple[list[dict], float]]) -> dict:
    """조건별 승률 기여도 분석. trades_breakdown: [(breakdown_list, r_multiple), ...]"""
    results: dict[str, dict] = {}
    for breakdown, r_multiple in trades_breakdown:
        is_win = r_multiple > 0
        for cond in breakdown:
            if cond.get("score", 0) < 100:  # 해당 조건 미충족이면 기여도 계산 대상 아님
                continue
            name = cond["name"]
            stats = results.setdefault(name, {"win": 0, "loss": 0})
            if is_win:
                stats["win"] += 1
            else:
                stats["loss"] += 1

    summary = {}
    for name, stats in results.items():
        total = stats["win"] + stats["loss"]
        summary[name] = {
            "win_rate_pct": round(stats["win"] / total * 100, 1) if total else None,
            "sample_size": total,
            "wins": stats["win"],
            "losses": stats["loss"],
        }
    return summary
