# XAU/USD Scalper Signal System

Python + Streamlit project for building an XAU/USD scalper signal dashboard using FCS API WebSocket data.

## Current phase

Phase 1 is a live-data foundation only:

- FCS WebSocket collector skeleton
- SQLite candle and quote storage
- Streamlit dashboard shell
- Safe environment-variable configuration
- No API keys committed to GitHub
- No trade execution
- No BUY/SELL signal engine yet

## Project structure

```text
.
├── app.py
├── requirements.txt
├── .env.example
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── fcs_ws_client.py
│   ├── candle_store.py
│   └── logger.py
├── data/
│   └── .gitkeep
└── tests/
    └── .gitkeep
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/marthandan77/xau.git
cd xau
```

### 2. Create virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set your FCS socket key:

```env
FCS_API_KEY=your_socket_key_here
FCS_WS_URL=wss://ws-v4.fcsapi.com/ws
FCS_SYMBOL=FX:XAUUSD
FCS_TIMEFRAMES=1,5,15
```

If your FCS account uses a different symbol format for gold, update `FCS_SYMBOL` accordingly.

## Run the collector

Start the WebSocket collector in one terminal:

```bash
python -m src.fcs_ws_client
```

The collector writes candles and quotes to:

```text
data/signals.db
```

## Run the dashboard

Open a second terminal and run:

```bash
streamlit run app.py
```

The dashboard shows:

- Connection status
- Current symbol
- Latest bid/ask/last price
- Spread
- Recent candle chart
- Recent candle table

## Phase roadmap

### Phase 1 — Live data foundation

Done in this scaffold.

### Phase 2 — Indicator engine

Planned modules:

- EMA 9/21/50
- VWAP
- ATR 14
- ATR average 20
- RSI 14
- Bollinger Bands 20, 2.0
- Keltner Channel 20, 1.5 ATR
- Squeeze ON/OFF
- Squeeze release up/down

### Phase 3 — Market structure engine

Planned detection:

- Swing high / swing low
- Break of structure up/down
- Liquidity sweep high/low
- VWAP reclaim/loss
- Chop/range filter

### Phase 4 — Signal engine

Planned output:

```text
Signal: BUY / SELL / NO TRADE
Mode: Squeeze breakout / Liquidity sweep reversal / Pullback continuation
Entry zone
Stop loss
TP1
TP2
Confidence score
Signal expiry
Reason
Invalidation
```

### Phase 5 — Risk and alerting

Planned controls:

- Spread filter
- News blackout placeholder
- Signal expiry
- No-chase rule
- Telegram/browser alert
- Signal log

## Trading safety

This project is for signal research and decision support only. It does not execute trades. XAU/USD scalping is high-risk and very sensitive to spread, slippage, news events, and broker execution quality.
