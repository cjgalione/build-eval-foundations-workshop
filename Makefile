# =============================================================================
# advanced-tracing-workshop — operator entry points
#
# Prereqs (install from WELCOME.md before running any target): uv, bt, gh.
# Auth/config: fill .env with the two API keys, then export BRAINTRUST_PROFILE +
# BRAINTRUST_DEFAULT_PROJECT (see WORKSHOP.md §4.2).
# See SEEDING_MILESTONES.md for the full build plan.
# =============================================================================

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# ANSI helpers
BOLD := \033[1m
DIM  := \033[2m
OK   := \033[32m
WARN := \033[33m
ERR  := \033[31m
END  := \033[0m

# Every target that talks to Braintrust needs a project. It comes from the shell
# export (WORKSHOP.md §4.2), which both bt and the Python code read.
PROJECT_GUARD = @test -n "$${BRAINTRUST_DEFAULT_PROJECT:-}" || { printf "$(ERR)Set BRAINTRUST_DEFAULT_PROJECT first (WORKSHOP.md §4.2):$(END) export BRAINTRUST_DEFAULT_PROJECT=<your-project>\n"; exit 1; }

# Full-seed size (override: `make seed COUNT=500`).
COUNT ?= 500

# Guard for targets whose script isn't written yet — points at the milestone.
define require_script
@test -f $(1) || { printf "$(WARN)$(1) not built yet — see SEEDING_MILESTONES.md $(2).$(END)\n"; exit 2; }
endef

# -----------------------------------------------------------------------------
.PHONY: help
help:
	@echo ""
	@printf "$(BOLD)advanced-tracing-workshop$(END) — make targets\n"
	@echo ""
	@printf "$(BOLD)Hero$(END)\n"
	@echo "  make prepare       ONE-SHOT: enable Topics → smoke seed → full seed (prepare a project)"
	@echo ""
	@printf "$(BOLD)Setup$(END)\n"
	@echo "  make setup         uv sync + create .env (checks uv/bt/gh are installed)"
	@echo "  make agent         run the agent's Streamlit app (live demo — §5.1)"
	@echo ""
	@printf "$(BOLD)Provision (pre-work, tool commented out)$(END)\n"
	@echo "  make topics        enable Topics on your project (M2)"
	@echo "  make seed-smoke    enable Topics (upstream) + seed 10 traces, then verify (M2→M3)"
	@echo "  make seed          seed COUNT traces (default 500; runs seed-smoke first) (M3)"
	@echo "  make provision     alias for seed-smoke — the topics + smoke verify gate"
	@echo "  make copy-dataset DATASET=<name>   copy a super-stonks dataset to all other org projects"
	@echo ""
	@printf "$(BOLD)Workshop (your own project)$(END)\n"
	@echo "  make curate-dataset  pull the gap cluster from super-stonks into a dataset in your project"
	@echo "  make push-scorer     push the grounded scorer online (prompt scorer)"
	@echo "  make automations     turn on the online automation for it (via API)"
	@echo "  (experiments run via: bt eval src/super_stonks/evals/qa_eval.py)"
	@echo ""

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
.PHONY: setup
setup:
	@command -v uv >/dev/null 2>&1 || { printf "$(ERR)uv not found.$(END) Install: curl -LsSf https://astral.sh/uv/install.sh | sh\n"; exit 1; }
	@command -v bt >/dev/null 2>&1 || printf "$(WARN)bt not found — install: curl -fsSL https://bt.dev/cli/install.sh | bash$(END)\n"
	@command -v gh >/dev/null 2>&1 || printf "$(WARN)gh not found — install: brew install gh (mac) / winget install GitHub.cli (win)$(END)\n"
	uv sync
	@if [ ! -f .env ]; then cp .env.example .env && printf "$(OK)Created .env — fill in OPENAI_API_KEY and BRAINTRUST_API_KEY.$(END)\n"; else printf "$(DIM).env already exists — leaving it.$(END)\n"; fi
	@printf "$(OK)Setup complete.$(END) Next: fill .env, then export BRAINTRUST_PROFILE + BRAINTRUST_DEFAULT_PROJECT (WORKSHOP.md §4.2).\n"

# -----------------------------------------------------------------------------
# Live demo
# -----------------------------------------------------------------------------
.PHONY: agent
agent:
	uv run streamlit run src/super_stonks/app.py

# -----------------------------------------------------------------------------
# Provision
# -----------------------------------------------------------------------------
.PHONY: topics
topics:
	$(PROJECT_GUARD)
	@printf "$(DIM)Enabling Topics on $$BRAINTRUST_DEFAULT_PROJECT …$(END)\n"
	-bt topics config enable --name "Workshop Topics" --topic-window 1d --generation-cadence 1h --no-input

# Topics is upstream of any seeding, so seed-smoke depends on it; the full seed
# depends on seed-smoke. Running `make seed` therefore does: topics → 10 smoke → 1,000.
.PHONY: seed-smoke
seed-smoke: topics
	$(PROJECT_GUARD)
	$(call require_script,src/super_stonks/seed/seed.py,M3)
	uv run python -m super_stonks.seed.seed --count 10
	@printf "$(OK)10 smoke traces sent.$(END) Verify: bt view logs --list-mode spans (Topics clustering), then 'make seed'.\n"

.PHONY: seed
seed: seed-smoke
	$(PROJECT_GUARD)
	$(call require_script,src/super_stonks/seed/seed.py,M3)
	uv run python -m super_stonks.seed.seed --count $(COUNT)

# Provision = the topics + smoke verify gate (alias for seed-smoke).
.PHONY: provision
provision: seed-smoke
	@printf "$(OK)Provisioned:$(END) Topics enabled + 10 smoke traces. Verify the gate, then run 'make seed'.\n"

# Hero one-shot: prepare a project end to end. The dependency chain runs
# topics → seed-smoke (10) → seed (1,000); this target just adds the headline.
# Prereqs: `make setup` + the WORKSHOP.md §4.2 exports (profile + project) done first.
.PHONY: prepare
prepare: seed
	@printf "$(OK)✔ Project prepared$(END) on $$BRAINTRUST_DEFAULT_PROJECT: Topics enabled, smoke + full traces seeded (tool gap in place).\n"

# Copy a dataset from the primary project (super-stonks) to every other org project.
# bt enumerates projects (profile auth); the SDK copies the rows.
.PHONY: copy-dataset
copy-dataset:
	@test -n "$(DATASET)" || { printf "$(ERR)Usage: make copy-dataset DATASET=<name>$(END)\n"; exit 1; }
	uv run python -m super_stonks.provision.copy_dataset "$(DATASET)"

# -----------------------------------------------------------------------------
# Online scoring
# -----------------------------------------------------------------------------
# Push the grounded scorer online (the reveal). Prompt scorer = no code bundling,
# so no --requirements; --runner points bt at the venv python so the
# definition-collection import (braintrust) resolves.
.PHONY: push-scorer
push-scorer:
	$(PROJECT_GUARD)
	bt functions push --file src/super_stonks/evals/push_assets.py \
		--language python --runner "$(CURDIR)/.venv/bin/python" \
		--if-exists replace -p "$$BRAINTRUST_DEFAULT_PROJECT" --yes

.PHONY: curate-dataset
curate-dataset:
	$(PROJECT_GUARD)
	uv run python -m super_stonks.provision.curate_dataset

.PHONY: automations
automations:
	$(PROJECT_GUARD)
	uv run python -m super_stonks.provision.configure
