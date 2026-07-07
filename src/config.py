"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import tuple

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the XAU/USD scalper system."""

    fcs_api_key: str
    fcs_ws_url: str
    fcs_symbol: str
    fcs_timeframes: tuple[str, ...]
    db_path: Path
    log_level: str
    app_refresh_seconds: int


def _parse_timeframes(raw_value: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return values or ("1", "5", "15")


def get_settings() -> Settings:
    """Return settings using safe defaults for local development."""

    db_path = Path(os.getenv("DB_PATH", "data/signals.db"))

    return Settings(
        fcs_api_key=os.getenv("FCS_API_KEY", "fcs_socket_demo"),
        fcs_ws_url=os.getenv("FCS_WS_URL", "wss://ws-v4.fcsapi.com/ws"),
        fcs_symbol=os.getenv("FCS_SYMBOL", "FX:XAUUSD"),
        fcs_timeframes=_parse_timeframes(os.getenv("FCS_TIMEFRAMES", "1,5,15")),
        db_path=db_path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        app_refresh_seconds=max(1, int(os.getenv("APP_REFRESH_SECONDS", "3"))),
    )
