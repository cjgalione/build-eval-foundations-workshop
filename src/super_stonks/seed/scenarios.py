"""Seed scenarios — a weighted mix of user questions for the Super Stonks agent.

~20% are realtime-price asks: THE GAP. With `get_stock_performance` commented out the
agent can't answer them, so they cluster in Topics and (once the grounding scorer is
built) score low. The rest give the project realistic variety.

`build(count)` returns a list of `{"bucket": str, "turns": [user_msg, ...]}` — one entry
per session/trace. Deterministic given `seed` so runs are reproducible.
"""

import random

TICKERS = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "AMD", "NFLX", "INTC", "JPM", "DIS"]

# (bucket, weight, templates). {t}/{t2} are filled with tickers.
_BUCKETS = [
    ("realtime_price", 0.20, [   # THE GAP — no tool to answer these
        "What is {t} trading at right now?",
        "Give me the current share price of {t}.",
        "How much is {t} stock today?",
        "What's the latest price on {t}?",
        "Quote for {t}?",
    ]),
    ("research", 0.22, [
        "Should I buy, hold, or sell {t} right now?",
        "Is {t} a good buy at the moment?",
        "Give me a buy/hold/sell call on {t} with the signals.",
        "What do the technicals say about {t}?",
    ]),
    ("performance", 0.15, [
        "How has {t} performed this year?",
        "What's {t} done over the past week?",
        "Has {t} been up or down lately?",
    ]),
    ("compare", 0.08, [
        "Compare {t} and {t2}.",
        "Which is the better buy, {t} or {t2}?",
    ]),
    ("concept", 0.20, [
        "Explain what a P/E ratio means.",
        "What's the difference between an ETF and a mutual fund?",
        "How do dividends work?",
        "What is dollar-cost averaging?",
        "Explain a Roth IRA vs a traditional IRA.",
        "What is an RMD?",
    ]),
    ("budgeting", 0.10, [
        "How much should I keep in an emergency fund?",
        "Any tips for paying down credit-card debt?",
        "How do capital-gains taxes work when I sell a stock?",
    ]),
    ("account_action", 0.05, [   # out-of-scope; agent should decline / escalate
        "Roll my 401k into a Roth IRA for me.",
        "Withdraw $5,000 from my brokerage account.",
        "Close my account.",
    ]),
]


# Follow-up turns for multi-turn sessions (keep the same conversational thread).
_FOLLOWUPS = [
    "What are the biggest risks there?",
    "How about {t2}?",
    "Why do you say that?",
    "Should I act now or wait?",
    "Can you summarize that in one line?",
    "And over a longer horizon?",
]


def _fill(template: str, rng: random.Random) -> str:
    t = rng.choice(TICKERS)
    t2 = rng.choice([x for x in TICKERS if x != t])
    return template.replace("{t2}", t2).replace("{t}", t)


def build(count: int, seed: int = 0) -> list[dict]:
    """Proportional (stratified) allocation, so even a 10-trace smoke gets its share of
    every bucket — including the realtime-price gap — instead of an unlucky random draw
    dropping it entirely."""
    rng = random.Random(seed)

    # Largest-remainder apportionment of `count` across buckets by weight.
    targets = [(b, weight * count, tmpls) for b, weight, tmpls in _BUCKETS]
    counts = {b: int(x) for b, x, _ in targets}
    leftover = count - sum(counts.values())
    for _, b in sorted(((x - int(x), b) for b, x, _ in targets), reverse=True)[:leftover]:
        counts[b] += 1

    templates_by_bucket = {b: tmpls for b, _, tmpls in _BUCKETS}
    scenarios: list[dict] = []
    for bucket, n in counts.items():
        for _ in range(n):
            scenarios.append({"bucket": bucket, "turns": [_fill(rng.choice(templates_by_bucket[bucket]), rng)]})
    rng.shuffle(scenarios)

    # Mix in multi-turn sessions: ~60% single-turn, ~25% two-turn, ~15% three-turn.
    for scenario in scenarios:
        r = rng.random()
        extra = 1 if r < 0.25 else 2 if r < 0.40 else 0
        for _ in range(extra):
            scenario["turns"].append(_fill(rng.choice(_FOLLOWUPS), rng))
    return scenarios
