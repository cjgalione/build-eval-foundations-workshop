from __future__ import annotations

import yfinance as yf
from braintrust import traced
from braintrust.span_types import SpanTypeAttribute

TOOLS_SPEC = [
    # ─────────────────────────────────────────────────────────────────────────────
    # THE GAP (workshop): get_stock_performance is the Yahoo/yfinance tool that pulls
    # real price data. Uncomment this entry (and its route in agent.py::_invoke_tool)
    # to show the feature change that closes the gap.
    {
        "type": "function",
        "function": {
            "name": "get_stock_performance",
            "description": (
                "Get the price performance of a publicly traded stock for the day, "
                "week, and year. Returns current price and percent change for each period."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol, e.g. AAPL, GOOGL, MSFT, TSLA",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "analyze_stock_buy",
            "description": (
                "Analyze whether a stock is a buy, hold, or sell using technical and "
                "fundamental signals: RSI, moving average crossover, 52-week range "
                "position, and analyst consensus."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol, e.g. AAPL, GOOGL, MSFT, TSLA",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
]


@traced(span_attributes={"type": SpanTypeAttribute.TOOL})
def get_stock_performance(ticker: str) -> dict:
    stock = yf.Ticker(ticker.upper())
    hist = stock.history(period="1y")

    if hist.empty:
        return {"error": f"No price data found for '{ticker}'. Check the ticker symbol."}

    current_price = float(hist["Close"].iloc[-1])
    day_open = float(hist["Open"].iloc[-1])

    week_ago_price = float(hist["Close"].iloc[-6] if len(hist) >= 6 else hist["Close"].iloc[0])
    year_ago_price = float(hist["Close"].iloc[0])

    return {
        "ticker": ticker.upper(),
        "current_price": round(current_price, 2),
        "currency": "USD",
        "day_change_pct": round((current_price - day_open) / day_open * 100, 2),
        "week_change_pct": round((current_price - week_ago_price) / week_ago_price * 100, 2),
        "year_change_pct": round((current_price - year_ago_price) / year_ago_price * 100, 2),
    }


@traced(span_attributes={"type": SpanTypeAttribute.TOOL})
def analyze_stock_buy(ticker: str) -> dict:
    stock = yf.Ticker(ticker.upper())
    info = stock.info
    hist = stock.history(period="1y")

    if hist.empty:
        return {"error": f"No data found for '{ticker}'. Check the ticker symbol."}

    signals: dict = {}
    buy_count = 0
    total = 0

    # RSI (14-day): neutral zone (30–70) is a bullish signal
    delta = hist["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - 100 / (1 + gain / loss)).iloc[-1])
    signals["rsi_14"] = round(rsi, 1)
    total += 1
    if 30 < rsi < 70:
        buy_count += 1

    # Golden/death cross: 50-day MA above 200-day MA is bullish
    if len(hist) >= 200:
        ma50 = float(hist["Close"].rolling(50).mean().iloc[-1])
        ma200 = float(hist["Close"].rolling(200).mean().iloc[-1])
        signals["ma50_above_ma200"] = ma50 > ma200
        total += 1
        if ma50 > ma200:
            buy_count += 1

    # 52-week position: below 60% of range is bullish (room to run)
    low_52w = info.get("fiftyTwoWeekLow")
    high_52w = info.get("fiftyTwoWeekHigh")
    current = info.get("currentPrice") or info.get("regularMarketPrice")
    if low_52w and high_52w and current and high_52w > low_52w:
        pos = (current - low_52w) / (high_52w - low_52w)
        signals["52w_position"] = round(pos, 2)
        total += 1
        if pos < 0.6:
            buy_count += 1

    # Analyst consensus: mean ≤ 2.5 is buy territory (scale: 1=strong buy, 5=strong sell)
    rec = info.get("recommendationMean")
    if rec:
        signals["analyst_rec_mean"] = round(rec, 2)
        total += 1
        if rec <= 2.5:
            buy_count += 1

    ratio = buy_count / total if total else 0
    verdict = "BUY" if ratio >= 0.6 else ("SELL" if ratio <= 0.35 else "HOLD")

    return {
        "ticker": ticker.upper(),
        "verdict": verdict,
        "bullish_signals": buy_count,
        "total_signals": total,
        "signals": signals,
    }
