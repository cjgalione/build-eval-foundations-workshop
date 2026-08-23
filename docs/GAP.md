# Closing the tool gap

**Read this when the user asks you to give the agent the ability to fetch real/live
stock prices, "add the missing tool", "fill the gap", "ground the answers in real
data", or otherwise fix why the agent makes up prices.**

## Background (why the gap exists)

This is a Braintrust workshop. The **Super Stonks** agent (`src/super_stonks/`) is a
LangGraph stock assistant. Realtime-price questions ("what's AAPL trading at?") are
**intentionally broken**: the tool that pulls real prices from Yahoo/yfinance,
`get_stock_performance`, is commented out. With no tool, the model answers from
parametric knowledge — ungrounded and often wrong. That is *the gap*, and closing it
is the workshop's before/after moment.

The offline scorer `price_response_matches_tool_data` (in
`src/super_stonks/evals/scorers.py`) measures whether the final answer states the
current price returned by the traced tool. With the tool off it scores `0`; closing the
gap should move it up.

## What to do (exactly two uncomments — do not reimplement anything)

The `@traced def get_stock_performance(ticker)` function **already exists and works**
(it calls yfinance for current price + day/week/year %). Do **not** rewrite it. You only
re-enable it. Both spots are marked with a `THE GAP` comment banner.

1. **`src/super_stonks/agent/tools.py`** — uncomment the `get_stock_performance` entry
   inside `TOOLS_SPEC` (the commented dict under the `THE GAP` banner). This re-exposes
   the tool to the LLM.

2. **`src/super_stonks/agent/agent.py`** — in `_invoke_tool`, uncomment the
   `get_stock_performance` route (the commented `if fn_name == "get_stock_performance"`
   under the `THE GAP` banner). This lets the tool call actually execute.

Leave `analyze_stock_buy` alone — it's unrelated to the price-grounding gap.

## Don't

- Don't add a new/different data source, API, or library — `get_stock_performance`
  already uses yfinance.
- Don't change span names, the package layout, or `analyze_stock_buy`.
- Don't push a prompt to Braintrust (the agent uses the hardcoded `STOCK_CHAT_SYSTEM`).

## After closing the gap

The workshop compares two experiments on the same dataset/scorer: baseline (tool off)
vs. fixed (tool on). See `SEEDING_MILESTONES.md` (M5–M6) for the experiment + online-score
follow-up.
