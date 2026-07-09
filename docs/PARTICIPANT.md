# Super Stonks — Participant Guide

Follow top to bottom. You **read** the shared, pre-seeded `super-stonks` project; you
**write** (dataset, experiments, online score) to **your own** project.

## 1. Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh          # uv
curl -fsSL https://bt.dev/cli/install.sh | bash          # bt
bt --version                                             # verify installation and version >= 0.15.1
brew install gh                                          # gh (or: winget install GitHub.cli)
```

## 2. Configure

```bash
git clone git@github.com:braintrustdata/advanced-tracing-workshop.git && cd advanced-tracing-workshop
make setup  # uv sync + creates .env
```

Fill in the .env file with the two keys from the workshop:

```bash
# .env — paste the two keys from the workshop:
#   OPENAI_API_KEY=...
#   BRAINTRUST_API_KEY=...
```

```bash
bt auth login  # use the workshop API key

# verify new workshop profile
bt auth profiles
```

```bash
export BRAINTRUST_PROFILE="workshop-advanced-tracing"
export BRAINTRUST_DEFAULT_PROJECT="<your-name>-stonks"  # YOUR project
```

```bash
bt setup skills                 
gh skill install braintrustdata/braintrust-skills agent-auto-improvement --agent claude-code
```

## 3. Run the agent, see your trace

```bash
make agent
```

```bash
bt view logs  # your project — open the trace you just made
```

## 4. Explore Topics on the shared seed

* NOTE: participants do not have access to the Braintrust UI, so this is instructor led.
```bash
bt topics open --project super-stonks
```

Target the **"Current stock price analysis"** cluster.

## 5. Investigate it with your coding agent

Ask your coding agent:

```bash
How are traces performing in the "Current stock price analysis" topic cluster in
'super-stonks'? Pull a representative sample, compare what the user asked vs. how the
agent responded.
```

It finds the gap: price questions the agent can't answer — no realtime-price tool.

## 6. Curate the traces from the cluster into your dataset

Now, add 10 traces to a dataset in your own project for offline evaluation. Prompt your coding agent to do this.

```bash
/agent-auto-improvement Capture 10 traces from the "Current stock price analysis" cluster as a dataset 'current-price-gap-offline'
 — the failure taxonomy/metadata is the price gap. Use /braintrust skill to capture traces and create a dataset.
```

Once the dataset is created, view it with:
```bash
bt datasets view current-price-gap-offline
```

## 7. Select a scorer and push it to your project

Evals require at least one scorer. We've already defined the scorer in the code.
We can push scorers to our Braintrust project.
This ensures versioned scorers are available across the team.

```bash
make push-scorer
```

Let's review our scorer we just pushed to our project.

```bash
bt scorers view
```

## 8. Baseline experiment (tool OFF)

`qa_eval.py` runs the agent over your dataset and scores each answer with the grounding
judge. 

```bash
EVAL_DATASET=current-price-gap-offline uv run bt eval src/super_stonks/evals/qa_eval.py
```

The run logs the experiment results.

## 9. Close the gap

Our agent is lacking a tool that can pull real-time stock prices from Yahoo Finance.
We have already written this tool in the code but it is currently disabled (commented out in the code).
We've specified in @GAP.md exactly where to uncomment it so the tool is usable by the agent.

Instruct your coding agent:

```bash
Fill the tool gap @GAP.md.
```

The tool is now included in the agents tools list.

Run the agent again to generate fresh traffic:

```bash
make agent
```

View the logs:

```bash
bt view logs
```

## 10. A/B test updated agent to previous version

```bash
EVAL_DATASET=current-price-gap-offline uv run bt eval src/super_stonks/evals/qa_eval.py
```

The new experiment should have a higher grounding score than the previous one.
This is a good sign that the tool is working and the agent is able to use it.

## 11. Enable online scoring automation for the new scorer

Now we want to enable online scoring automation for the new scorer.
This will automatically score new traces as they are logged to Braintrust.
This protects us from regressions in the future.

```bash   
make automations
```

## 12. Validate

Run the agent again to generate fresh traffic:
```bash
make agent
```

View the scoring added to the new trace in the logs:
```bash
bt view logs
```
