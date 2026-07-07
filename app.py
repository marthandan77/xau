"""Streamlit dashboard shell for the XAU/USD scalper project.

Phase 1 scope:
- Read locally stored FCS WebSocket data from SQLite.
- Show connection status, latest quote, and recent candles.
- Allow local FCS API key setup through the dashboard.
- Do not generate signals yet.
- Do not execute trades.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.candle_store import CandleStore
from src.config import get_settings


ENV_PATH = Path(".env")


def _read_env_lines() -> list[str]:
    if not ENV_PATH.exists():
        example = Path(".env.example")
        if example.exists():
            return example.read_text(encoding="utf-8").splitlines()
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _upsert_env_value(key: str, value: str) -> None:
    """Write one key/value into local .env without printing the secret."""

    lines = _read_env_lines()
    updated = False
    output: list[str] = []

    for line in lines:
        if line.startswith(f"{key}="):
            output.append(f"{key}={value}")
            updated = True
        else:
            output.append(line)

    if not updated:
        output.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


settings = get_settings()
store = CandleStore(settings.db_path)


st.set_page_config(
    page_title="XAU/USD Scalper",
    page_icon="📈",
    layout="wide",
)

st.title("XAU/USD Scalper Signal System")
st.caption("Phase 1: live data foundation only. No trade execution.")

with st.sidebar:
    st.header("FCS API setup")
    st.caption("Saved locally to .env. This file is ignored by Git.")
    fcs_key_input = st.text_input("FCS API key", type="password", placeholder="Paste key here")
    save_key = st.button("Save FCS key to .env", use_container_width=True)
    if save_key:
        cleaned_key = fcs_key_input.strip()
        if cleaned_key:
            _upsert_env_value("FCS_API_KEY", cleaned_key)
            st.success("FCS key saved locally. Restart the collector to use the new key.")
        else:
            st.error("Paste a valid key before saving.")

    st.divider()
    st.header("Controls")
    selected_timeframe = st.selectbox(
        "Candle timeframe",
        options=list(settings.fcs_timeframes),
        index=min(1, len(settings.fcs_timeframes) - 1),
    )
    candle_limit = st.slider("Candles to display", 25, 300, 100, step=25)
    auto_refresh = st.checkbox("Auto refresh", value=True)
    refresh_seconds = st.number_input(
        "Refresh seconds",
        min_value=1,
        max_value=30,
        value=settings.app_refresh_seconds,
        step=1,
    )

st.subheader("Connection")
status = store.get_connection_status()
status_cols = st.columns(3)
status_cols[0].metric("Status", str(status.get("status") or "unknown"))
status_cols[1].metric("Symbol", settings.fcs_symbol)
status_cols[2].metric("Updated", str(status.get("updated_at") or "-"))
if status.get("message"):
    st.info(str(status["message"]))

st.subheader("Latest quote")
quote = store.latest_quote(settings.fcs_symbol)
quote_cols = st.columns(4)
if quote:
    bid = quote.get("bid")
    ask = quote.get("ask")
    close = quote.get("close")
    spread = None
    if bid is not None and ask is not None:
        spread = float(ask) - float(bid)

    quote_cols[0].metric("Bid", f"{bid:.2f}" if bid is not None else "-")
    quote_cols[1].metric("Ask", f"{ask:.2f}" if ask is not None else "-")
    quote_cols[2].metric("Last", f"{close:.2f}" if close is not None else "-")
    quote_cols[3].metric("Spread", f"{spread:.2f}" if spread is not None else "-")
else:
    st.warning("No quote received yet. Start the collector: python -m src.fcs_ws_client")

st.subheader(f"Recent {selected_timeframe} minute candles")
candles = store.latest_candles(settings.fcs_symbol, selected_timeframe, limit=candle_limit)

if candles.empty:
    st.warning("No candles received yet. Start the collector and confirm your FCS symbol/timeframe.")
else:
    candles = candles.copy()
    candles["datetime"] = pd.to_datetime(candles["timestamp"], unit="s", utc=True)
    candles["datetime_local"] = candles["datetime"].dt.tz_convert("Asia/Singapore")

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=candles["datetime_local"],
                open=candles["open"],
                high=candles["high"],
                low=candles["low"],
                close=candles["close"],
                name="XAU/USD",
            )
        ]
    )
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    display_cols = [
        "datetime_local",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
    ]
    st.dataframe(candles[display_cols].tail(20), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Signal engine")
st.info(
    "Phase 1 does not generate BUY/SELL signals yet. "
    "Phase 2 will add indicators; Phase 3 will add the scalper signal engine."
)

st.caption(
    f"Last dashboard refresh: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
)

if auto_refresh:
    time.sleep(int(refresh_seconds))
    st.rerun()
