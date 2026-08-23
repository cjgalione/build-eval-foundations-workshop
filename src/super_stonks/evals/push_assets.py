"""Push the online price-response-quality proxy scorer.

This is the workshop's reveal (WORKSHOP.md §16), run **after** the offline experiments
show the agent's baseline and fixed behavior — not part of attendee setup. It measures
answer completeness, not proof that a price came from a tool.

It's a prompt scorer (declarative `messages`/`model`/`choice_scores`, no code bundling),
using the same editable UI criterion in `judge_prompts.py`.

Push with `make push-scorer`.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from braintrust import projects

from super_stonks.evals.judge_prompts import GRANULAR_SCORES, PRICE_RESPONSE_QUALITY_PROMPT

PROJECT = os.environ["BRAINTRUST_DEFAULT_PROJECT"]
project = projects.create(name=PROJECT)

project.scorers.create(
    name="price_response_completeness",
    slug="price_response_completeness",
    messages=[{"role": "user", "content": PRICE_RESPONSE_QUALITY_PROMPT}],
    model="gpt-4o",
    use_cot=True,
    choice_scores=GRANULAR_SCORES,
    if_exists="replace",
)
