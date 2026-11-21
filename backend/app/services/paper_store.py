"""SQLite-backed paper trading ledger. Tiny, dependency-free (stdlib sqlite3)."""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_PATH = os.getenv("PAPER_DB_PATH", os.path.join(PROJECT_ROOT, "paper.db"))

_LOCK = threading.Lock()
_INITIAL_CASH = 100_000.0


SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    qty REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);

CREATE TABLE IF NOT EXISTS positions (
    ticker TEXT PRIMARY KEY,
    qty REAL NOT NULL,
    avg_cost REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    cash REAL NOT NULL
);
"""


@dataclass
class Trade:
    id: int
    ts: int
    ticker: str
    side: str
    qty: float
    price: float
    fee: float


@dataclass
class Position:
    ticker: str
    qty: float
    avg_cost: float


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _LOCK, _conn() as c:
        c.executescript(SCHEMA)
        row = c.execute("SELECT cash FROM portfolio WHERE id = 1").fetchone()
        if row is None:
            c.execute("INSERT INTO portfolio(id, cash) VALUES (1, ?)", (_INITIAL_CASH,))


def get_cash() -> float:
    with _LOCK, _conn() as c:
        row = c.execute("SELECT cash FROM portfolio WHERE id = 1").fetchone()
        return float(row["cash"]) if row else _INITIAL_CASH


def list_positions() -> List[Position]:
    with _LOCK, _conn() as c:
        rows = c.execute("SELECT ticker, qty, avg_cost FROM positions WHERE qty > 0").fetchall()
        return [Position(ticker=r["ticker"], qty=r["qty"], avg_cost=r["avg_cost"]) for r in rows]


def list_trades(limit: int = 50, ticker: Optional[str] = None) -> List[Trade]:
    with _LOCK, _conn() as c:
        if ticker:
            rows = c.execute(
                "SELECT * FROM trades WHERE ticker = ? ORDER BY ts DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM trades ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            Trade(
                id=r["id"],
                ts=r["ts"],
                ticker=r["ticker"],
                side=r["side"],
                qty=r["qty"],
                price=r["price"],
                fee=r["fee"],
            )
            for r in rows
        ]


def execute_trade(ticker: str, side: str, qty: float, price: float, fee_bps: float = 10.0) -> Trade:
    """fee_bps in basis points of notional (10 bps = 0.10%)."""
    side = side.lower().strip()
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    if qty <= 0 or price <= 0:
        raise ValueError("qty and price must be positive")

    notional = qty * price
    fee = notional * (fee_bps / 10_000.0)
    ts = int(time.time())

    with _LOCK, _conn() as c:
        cur = c.execute("SELECT cash FROM portfolio WHERE id = 1")
        cash = float(cur.fetchone()["cash"])

        pos_row = c.execute("SELECT qty, avg_cost FROM positions WHERE ticker = ?", (ticker,)).fetchone()
        pos_qty = float(pos_row["qty"]) if pos_row else 0.0
        pos_avg = float(pos_row["avg_cost"]) if pos_row else 0.0

        if side == "buy":
            cost = notional + fee
            if cash < cost:
                raise ValueError(f"Insufficient cash: need {cost:.2f}, have {cash:.2f}")
            new_qty = pos_qty + qty
            new_avg = ((pos_qty * pos_avg) + notional) / new_qty if new_qty > 0 else 0.0
            new_cash = cash - cost
        else:
            if pos_qty < qty:
                raise ValueError(f"Insufficient position: have {pos_qty}, need {qty}")
            new_qty = pos_qty - qty
            new_avg = pos_avg if new_qty > 0 else 0.0
            new_cash = cash + notional - fee

        cur = c.execute(
            "INSERT INTO trades(ts, ticker, side, qty, price, fee) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, ticker, side, qty, price, fee),
        )
        trade_id = cur.lastrowid
        if pos_row is None:
            c.execute("INSERT INTO positions(ticker, qty, avg_cost) VALUES (?, ?, ?)", (ticker, new_qty, new_avg))
        else:
            c.execute("UPDATE positions SET qty = ?, avg_cost = ? WHERE ticker = ?", (new_qty, new_avg, ticker))
        c.execute("UPDATE portfolio SET cash = ? WHERE id = 1", (new_cash,))

    return Trade(id=trade_id, ts=ts, ticker=ticker, side=side, qty=qty, price=price, fee=fee)


def reset_portfolio() -> None:
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM trades")
        c.execute("DELETE FROM positions")
        c.execute("UPDATE portfolio SET cash = ? WHERE id = 1", (_INITIAL_CASH,))


init_db()
