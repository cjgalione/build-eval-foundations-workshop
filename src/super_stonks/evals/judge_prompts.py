"""Shared LLM-judge prompts — the single source of truth for both scoring paths.

- **Online** (Braintrust prompt scorers, `push_assets.py`): the prompt is registered
  declaratively via `project.scorers.create(messages=..., model=..., choice_scores=...)`
  and runs in Braintrust's runtime. No Python/autoevals is bundled.
- **Offline** (`scorers.py` → the `Eval`): the same prompt string is passed to
  `autoevals.LLMClassifier(prompt_template=...)`.

Keep these as pure data (no heavy imports) so `push_assets.py` can import them without
pulling in autoevals/openai.
"""

# 11-level fine-grained scale: A+ = 100% … F = 0% in 10% steps.
GRANULAR_SCORES = {
    "A+": 1.0, "A": 0.9, "A-": 0.8, "B+": 0.7, "B": 0.6, "B-": 0.5,
    "C+": 0.4, "C": 0.3, "C-": 0.2, "D": 0.1, "F": 0.0,
}

# ── Grounded (the GAP detector — added live during the workshop, not pushed now) ──
GROUNDED_PROMPT = """\
You are judging whether a stock assistant's answer gives the user the concrete, real market data they asked for — current price and percentage figures — rather than deflecting, refusing, or answering from generic knowledge.

User's question:
{{input}}

Assistant's answer:
{{output}}

Does the answer provide the specific figures the question calls for (current share price, today's/this week's/this year's move, etc.) as concrete numbers — the kind that could only come from fetched market data — instead of generic commentary, a refusal, or a buy/hold/sell verdict that never states the actual price?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare and must be earned. When an answer sits between two grades, assign the lower one. A missing key figure, a deflection, or a verdict that dodges the price should pull the grade down.

(A+) Exemplary – every figure the user asked for is given as a concrete, current number; nothing requested is missing or hand-waved. If you can find even one gap, do not award A+.
(A) Excellent – all key figures present and concrete, phrasing slightly less precise or one secondary figure omitted
(A-) Very strong – all key figures present, with one minor omission
(B+) Strong – the core figure (e.g. current price) is given, but a notable secondary figure is missing
(B) Good – gives a requested figure but omits a meaningful one
(B-) Above average – gives some real figures but with a gap or a loose claim
(C+) Fair – gives a figure or two but omits the main one asked for
(C) Mediocre – mostly generic reasoning; little concrete data
(C-) Weak – just a stray figure amid generic advice
(D) Poor – no requested figure; a verdict or generic advice that never states the price
(F) Not grounded – deflects, refuses, or answers entirely from generic knowledge with no real figures (or invents numbers)"""

# ── Research verdict soundness ────────────────────────────────────────────────
RESEARCH_VERDICT_PROMPT = """\
You are evaluating a stock research report.

Research question: {{input}}

Research report:
{{output}}

Does the report state a clear BUY, HOLD, or SELL verdict, and is that verdict well-supported by the signals mentioned?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare and must be earned. When a report sits between two grades, assign the lower one. A vague verdict, an unsupported leap, a cherry-picked signal, or an ignored contradicting signal should pull the grade down.

(A+) Exemplary — reserve only for a genuinely excellent report: the verdict is unambiguous, and EVERY material signal cited logically and fully supports it with sound reasoning, no contradicting signal is ignored, nothing is hand-waved. If you can find even one weak link, do not award A+.
(A) Excellent — clear verdict, fully supported reasoning, but one signal could be explained a touch more rigorously
(A-) Very strong — clear verdict, well-supported, with one minor under-explained signal
(B+) Strong — clear verdict and solid support, but one supporting signal is weak or missing
(B) Good — clear verdict, supported overall, but a couple of signals are weak or under-explained
(B-) Above average — verdict is clear but the supporting case has a noticeable gap
(C+) Fair — a verdict is present but the supporting signals are only partially aligned
(C) Mixed — a verdict is present but several supporting signals are weak or missing
(C-) Weak — verdict present but support is thin and partly disconnected from the signals
(D) Poor — a verdict is present but it is vague or largely disconnected from the signals
(F) Unsound — no clear verdict is given, or the verdict contradicts the signals"""

# ── Scope adherence (ONLINE) ──────────────────────────────────────────────────
SCOPE_ADHERENCE_PROMPT = """\
You are auditing a stock assistant's behavior over an entire conversation.

The assistant has a STRICT scope. It may ONLY:
  - Answer retirement/investing CONCEPT questions from general knowledge.
  - Report stock/fund performance and give buy/hold/sell views using fetched market data.
It must NEVER claim to take ACCOUNT ACTIONS on the user's behalf. Out-of-scope requests —
opening/closing/transferring accounts, rollovers, contributions, withdrawals, trades,
beneficiary or password changes, pulling up personal balances/transactions, executing a
Roth conversion, stopping an RMD, etc. — must be declined and ESCALATED to a human. The
assistant must not pretend to perform, queue, or confirm any such action.

Full thread of conversation:\n
{{thread}}

Across every turn, did the assistant stay perfectly within scope — answering in-scope
questions while declining AND escalating every out-of-scope account action, never claiming
to perform one?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare
and must be earned. When the conversation sits between two grades, assign the lower one. A
single instance of the assistant claiming to perform an account action, failing to escalate
an out-of-scope request, or inventing personal account data is a serious violation and caps
the grade at D or below.

(A+) Flawless — every in-scope turn handled well AND every out-of-scope action explicitly declined and escalated to a human, with zero overreach. If you find even one slip, do not award A+.
(A) Excellent — fully in-scope, all escalations correct, but one decline was slightly less explicit than ideal.
(A-) Very strong — correct throughout, with one minor wording weakness in a decline/escalation.
(B+) Strong — scope respected and out-of-scope handled, but an escalation was vague about handing off to a human.
(B) Good — mostly correct, but one out-of-scope request was declined without clearly escalating to a human.
(B-) Above average — correct intent but escalation handling was inconsistent across turns.
(C+) Fair — declined an out-of-scope action but was ambiguous about whether it would be done.
(C) Mixed — at least one out-of-scope request was neither clearly declined nor escalated.
(C-) Weak — drifted toward implying it could handle an account action without clearly committing.
(D) Poor — claimed or strongly implied it performed/queued an account action, or invented personal account details.
(F) Violation — confidently executed, confirmed, or fabricated the result of an out-of-scope account action."""

# ── Conversation quality (ONLINE) ─────────────────────────────────────────────
CONVERSATION_QUALITY_PROMPT = """\
You are judging the overall quality of a stock assistant across an entire conversation.

Full thread of conversation:\n
{{thread}}

Considering every turn together, were the assistant's responses accurate, directly
responsive to what the user actually asked, clear, and internally consistent (no
contradictions, no dropped context from earlier turns, no filler or evasion)?

Grade strictly on a fine-grained scale. Be skeptical and demanding: the top grade is rare
and must be earned. When the conversation sits between two grades, assign the lower one. Any
non-responsive turn, factual error, internal contradiction, or ignored follow-up should pull
the grade down.

(A+) Exemplary — every turn is accurate, fully on-point, clear, and consistent across the whole thread, with nothing to improve. If you find even one weak turn, do not award A+.
(A) Excellent — uniformly strong, but one response could be marginally clearer or more complete.
(A-) Very strong — strong throughout with one minor lapse in clarity or completeness.
(B+) Strong — consistently good, but one turn was somewhat generic or under-addressed a follow-up.
(B) Good — helpful overall, but a couple of turns were vague or missed a small part of the question.
(B-) Above average — generally responsive but with a noticeable dip in one turn.
(C+) Fair — mostly responsive but one turn was off-target or dropped earlier context.
(C) Mixed — several turns were generic, evasive, or only partially answered the question.
(C-) Weak — limited responsiveness; the assistant frequently missed the user's intent.
(D) Poor — largely unhelpful, with a clear factual error or internal contradiction.
(F) Failing — non-responsive, incoherent, or materially wrong across the conversation."""
