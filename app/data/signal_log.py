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
