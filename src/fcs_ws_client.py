"""FCS API WebSocket collector for XAU/USD candles and quotes.

Run with:
    python -m src.fcs_ws_client

This module only collects data. It does not generate trading signals or execute trades.
"""

from __future__ import annotations

import asyncio
import json
import signal
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import websockets
from websockets.exceptions import ConnectionClosed

from src.candle_store import Candle, CandleStore, Quote
from src.config import get_settings
from src.logger import setup_logger


class FCSWebSocketClient:
    """Minimal async collector for FCS API WebSocket v4."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.log = setup_logger(self.__class__.__name__, self.settings.log_level)
        self.store = CandleStore(self.settings.db_path)
        self._should_stop = asyncio.Event()

    def _ws_url_with_key(self) -> str:
        """Append access_key query parameter without logging the key."""

        parsed = urlparse(self.settings.fcs_ws_url)
        query = dict(parse_qsl(parsed.query))
        query["access_key"] = self.settings.fcs_api_key
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _subscribe_payload(self, symbol: str, timeframe: str) -> str:
        """Return the FCS join-symbol payload.

        FCS socket docs show subscription shape:
        {"type": "join_symbol", "symbol": "FX:EURUSD", "timeframe": "5"}
        """

        return json.dumps(
            {
                "type": "join_symbol",
                "symbol": symbol,
                "timeframe": timeframe,
            }
        )

    async def _subscribe_all(self, websocket: websockets.WebSocketClientProtocol) -> None:
        for timeframe in self.settings.fcs_timeframes:
            payload = self._subscribe_payload(self.settings.fcs_symbol, timeframe)
            await websocket.send(payload)
            self.log.info("Subscribed to %s timeframe=%s", self.settings.fcs_symbol, timeframe)

    def _handle_price(self, data: dict[str, Any]) -> None:
        prices = data.get("prices") or {}
        mode = prices.get("mode")
        symbol = data.get("symbol") or self.settings.fcs_symbol
        timeframe = str(data.get("timeframe") or "")

        if mode == "candle":
            required = ["t", "o", "h", "l", "c"]
            if not all(key in prices for key in required):
                self.log.warning("Skipping incomplete candle payload: %s", data)
                return

            candle = Candle(
                timestamp=int(prices["t"]),
                symbol=symbol,
                timeframe=timeframe,
                open=float(prices["o"]),
                high=float(prices["h"]),
                low=float(prices["l"]),
                close=float(prices["c"]),
                volume=float(prices["v"]) if prices.get("v") is not None else None,
            )
            self.store.upsert_candle(candle)
            self.log.debug(
                "Candle %s %s close=%s", candle.symbol, candle.timeframe, candle.close
            )
            return

        if mode == "askbid":
            timestamp = prices.get("update") or prices.get("t")
            if timestamp is None:
                self.log.warning("Skipping quote without timestamp: %s", data)
                return

            quote = Quote(
                timestamp=int(timestamp),
                symbol=symbol,
                timeframe=timeframe,
                bid=float(prices["b"]) if prices.get("b") is not None else None,
                ask=float(prices["a"]) if prices.get("a") is not None else None,
                close=float(prices["c"]) if prices.get("c") is not None else None,
            )
            self.store.insert_quote(quote)
            self.log.debug("Quote %s bid=%s ask=%s", quote.symbol, quote.bid, quote.ask)
            return

        self.log.debug("Unhandled price mode=%s payload=%s", mode, data)

    def _handle_message(self, data: dict[str, Any]) -> None:
        msg_type = data.get("type")

        if msg_type == "price":
            self._handle_price(data)
            return

        if msg_type == "welcome":
            self.log.info("FCS welcome received")
            self.store.set_connection_status("connected", "welcome received")
            return

        if msg_type == "message":
            short = data.get("short")
            message = data.get("message")
            self.log.info("FCS message short=%s message=%s", short, message)
            self.store.set_connection_status("connected", str(message))
            return

        if msg_type == "error":
            message = str(data.get("message") or data)
            self.log.error("FCS error: %s", message)
            self.store.set_connection_status("error", message)
            return

        self.log.debug("Unhandled message: %s", data)

    async def _run_once(self) -> None:
        url = self._ws_url_with_key()
        safe_url = self.settings.fcs_ws_url
        self.log.info("Connecting to %s", safe_url)
        self.store.set_connection_status("connecting", safe_url)

        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as websocket:
            self.log.info("WebSocket connected")
            self.store.set_connection_status("connected", "raw websocket connected")
            await self._subscribe_all(websocket)

            async for raw_message in websocket:
                if self._should_stop.is_set():
                    break

                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    self.log.warning("Non-JSON message received: %s", raw_message)
                    continue

                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            self._handle_message(item)
                    continue

                if isinstance(data, dict):
                    self._handle_message(data)
                else:
                    self.log.debug("Unsupported message payload: %s", data)

    async def run_forever(self) -> None:
        """Run collector with basic reconnect handling."""

        reconnect_delay_seconds = 5
        while not self._should_stop.is_set():
            try:
                await self._run_once()
            except ConnectionClosed as exc:
                message = f"connection closed: {exc}"
                self.log.warning(message)
                self.store.set_connection_status("disconnected", message)
            except OSError as exc:
                message = f"network error: {exc}"
                self.log.warning(message)
                self.store.set_connection_status("error", message)
            except Exception as exc:  # noqa: BLE001 - collector should not die silently
                message = f"unexpected error: {exc}"
                self.log.exception(message)
                self.store.set_connection_status("error", message)

            if not self._should_stop.is_set():
                self.log.info("Reconnecting in %s seconds", reconnect_delay_seconds)
                await asyncio.sleep(reconnect_delay_seconds)

    def stop(self) -> None:
        self.log.info("Shutdown requested")
        self._should_stop.set()
        self.store.set_connection_status("stopping", "shutdown requested")


async def _main() -> None:
    client = FCSWebSocketClient()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, client.stop)
        except NotImplementedError:
            # Windows event loop may not support signal handlers.
            pass

    await client.run_forever()


if __name__ == "__main__":
    asyncio.run(_main())
