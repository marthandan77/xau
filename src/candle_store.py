"""SQLite storage for live candles and ask/bid quotes."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd


@dataclass(frozen=True)
class Candle:
    timestamp: int
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    source: str = "fcsapi"


@dataclass(frozen=True)
class Quote:
    timestamp: int
    symbol: str
    timeframe: str
    bid: float | None
    ask: float | None
    close: float | None
    source: str = "fcsapi"


class CandleStore:
    """Small SQLite repository for candles and quotes."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL,
                    source TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (timestamp, symbol, timeframe)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quotes (
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    bid REAL,
                    ask REAL,
                    close REAL,
                    source TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (timestamp, symbol, timeframe)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connection_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    status TEXT NOT NULL,
                    message TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def upsert_candle(self, candle: Candle) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO candles (
                    timestamp, symbol, timeframe, open, high, low, close, volume, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(timestamp, symbol, timeframe)
                DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    source=excluded.source,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    candle.timestamp,
                    candle.symbol,
                    candle.timeframe,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.source,
                ),
            )

    def insert_quote(self, quote: Quote) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO quotes (
                    timestamp, symbol, timeframe, bid, ask, close, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quote.timestamp,
                    quote.symbol,
                    quote.timeframe,
                    quote.bid,
                    quote.ask,
                    quote.close,
                    quote.source,
                ),
            )

    def set_connection_status(self, status: str, message: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connection_status (id, status, message)
                VALUES (1, ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    status=excluded.status,
                    message=excluded.message,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (status, message),
            )

    def get_connection_status(self) -> dict[str, str | None]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status, message, updated_at FROM connection_status WHERE id = 1"
            ).fetchone()
        if row is None:
            return {"status": "unknown", "message": None, "updated_at": None}
        return dict(row)

    def latest_quote(self, symbol: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM quotes
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
        return dict(row) if row else None

    def latest_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> pd.DataFrame:
        with self._connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT timestamp, symbol, timeframe, open, high, low, close, volume, source
                FROM candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                conn,
                params=(symbol, timeframe, limit),
            )
        if df.empty:
            return df
        return df.sort_values("timestamp").reset_index(drop=True)
