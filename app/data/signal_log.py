"""신호 이력 저장 및 통계 (SQLite)"""
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "signal_history.db"

# 기존 배포된 DB에 새 컬럼을 안전하게 추가하기 위한 마이그레이션 목록
_MIGRATIONS = [
    "ALTER TABLE signal_log ADD COLUMN tp1 REAL",
    "ALTER TABLE signal_log ADD COLUMN tp2 REAL",
    "ALTER TABLE signal_log ADD COLUMN tp3 REAL",
    "ALTER TABLE signal_log ADD COLUMN outcome TEXT",       # NULL(미종료/관망) | '익절' | '손절' | '본전'
    "ALTER TABLE signal_log ADD COLUMN exit_price REAL",
    "ALTER TABLE signal_log ADD COLUMN r_multiple REAL",
    "ALTER TABLE signal_log ADD COLUMN resolved_at TEXT",
]


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
        for stmt in _MIGRATIONS:
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                pass  # 컬럼이 이미 존재 (재배포 시 정상 케이스)


def log_signal(signal) -> int:
    """신호를 기록하고 새로 생성된 row id를 반환 (승패 판정 대상 식별용)"""
    d = asdict(signal)
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO signal_log
               (signal_time, is_trade, position, confidence, current_price,
                entry_price, stop_loss, tp1, tp2, tp3, risk_reward, no_trade_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d["signal_time"], int(d["is_trade"]), d["position"], d["confidence"],
                d["current_price"], d["entry_price"], d["stop_loss"],
                d["tp1"], d["tp2"], d["tp3"], d["risk_reward"],
                None if d["is_trade"] else (d["reasons"][0] if d["reasons"] else None),
            ),
        )
        return cur.lastrowid


def get_pending_trades() -> list[dict]:
    """아직 승패 판정이 안 난 진입 신호 목록 (승패 자동 판정 대상)"""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM signal_log WHERE is_trade = 1 AND outcome IS NULL ORDER BY id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_trade_outcome(row_id: int, outcome: str, exit_price: float, r_multiple: float) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE signal_log SET outcome = ?, exit_price = ?, r_multiple = ?, resolved_at = ? WHERE id = ?",
            (outcome, exit_price, r_multiple, datetime.now(timezone.utc).isoformat(), row_id),
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

        wins = c.execute(
            "SELECT COUNT(*) n FROM signal_log WHERE signal_time >= ? AND is_trade = 1 AND outcome IS NOT NULL AND r_multiple > 0",
            (since,),
        ).fetchone()["n"]
        losses = c.execute(
            "SELECT COUNT(*) n FROM signal_log WHERE signal_time >= ? AND is_trade = 1 AND outcome IS NOT NULL AND r_multiple <= 0",
            (since,),
        ).fetchone()["n"]
        pending = c.execute(
            "SELECT COUNT(*) n FROM signal_log WHERE signal_time >= ? AND is_trade = 1 AND outcome IS NULL",
            (since,),
        ).fetchone()["n"]
        total_r = c.execute(
            "SELECT SUM(r_multiple) s FROM signal_log WHERE signal_time >= ? AND is_trade = 1 AND outcome IS NOT NULL",
            (since,),
        ).fetchone()["s"]

    resolved = wins + losses
    return {
        "period_hours": hours,
        "total_checks": total,
        "trade_signals": trades,
        "no_trade_count": total - trades,
        "trade_rate_pct": round(trades / total * 100, 2) if total else 0.0,
        "by_position": {r["position"]: r["n"] for r in by_position},
        "top_no_trade_reasons": [{"reason": r["no_trade_reason"], "count": r["n"]} for r in top_no_trade],
        "avg_confidence": round(avg_conf, 1) if avg_conf else 0.0,
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "win_rate_pct": round(wins / resolved * 100, 1) if resolved else None,
        "total_r": round(total_r, 2) if total_r else 0.0,
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
