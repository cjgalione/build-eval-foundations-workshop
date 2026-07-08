"""Push the grounding scorer to Braintrust as an online LLM-judge prompt scorer.

This is the workshop's reveal (WORKSHOP.md §16), run **after** the offline experiments
show the agent is ungrounded on price questions — not part of pre-seed provisioning.
Nothing else is pushed: attendees' fresh projects stay clean, and the only online score
is the one the story is about.

It's a prompt scorer (declarative `messages`/`model`/`choice_scores`, no code bundling),
sharing `GROUNDED_PROMPT` with the offline `LLMClassifier` in `scorers.py`.

Push with `make push-scorer`.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from braintrust import projects

from super_stonks.evals.judge_prompts import GRANULAR_SCORES, GROUNDED_PROMPT

PROJECT = os.environ.get("BRAINTRUST_DEFAULT_PROJECT", "super-stonks")
project = projects.create(name=PROJECT)

project.scorers.create(
    name="response_grounded_in_data",
    slug="response_grounded_in_data",
    messages=[{"role": "user", "content": GROUNDED_PROMPT}],
    model="gpt-4o",
    use_cot=True,
    choice_scores=GRANULAR_SCORES,
    if_exists="replace",
)
