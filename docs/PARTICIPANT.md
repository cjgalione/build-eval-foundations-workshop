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
git clone git@github.com:spencerseale/advanced-tracing-workshop.git && cd advanced-tracing-workshop
make setup  # uv sync + creates .env
```

Fill in the .env file with the two keys from the workshop:

```bash
# .env — paste the two keys from the workshop:
#   OPENAI_API_KEY=...
#   BRAINTRUST_API_KEY=...
```

Run the following command, then use the arrow keys to select `API Key` as the auth method. Paste your Braintrust API key to create the new login.
```bash
bt auth login
```

Quickly verify a new profile was successfully created.
```bash
bt auth profiles
```
You should see an output like `✓ workshop-advanced-tracing — api_key — org: workshop-advanced-tracing — sk-****gYyeM`.

Next, set the following so future commands have the right context to execute. Replace `<your-name>` with your name so you get your own project.
```bash
export BRAINTRUST_PROFILE="workshop-advanced-tracing"
export BRAINTRUST_DEFAULT_PROJECT="<your-name>-stonks"
```

Next, set up the Braintrust skills so coding agents know exactly how to interact with `bt`. Select `local` as the scope, press "Enter" to accept the default workflow docs, and choose the coding agent of your choice. We will be using Claude in this workshop, but all should work the same way.
```bash
bt setup skills 
```

Fetch the `agent-auto-improvement` skill from the Braintrust skills repository. Select `Project` as the installation scope.
```bash
gh skill install braintrustdata/braintrust-skills agent-auto-improvement --agent claude-code
```

## 3. Run the agent, see your trace

This repository contains a simple agent you'll use throughout to generate traces and interact with. Use the `make` command to launch it. It will open in your browser.

> **Note:** make sure you have `BRAINTRUST_API_KEY` and `OPENAI_API_KEY` set in `.env`, otherwise you will run into issues.
```bash
make agent
```
Once the Streamlit app opens and loads, ask a question in the chat input or select a "Starting point" from the left. When you've done some interacting, interrupt the app with Ctrl + C.

With some interactions logged, use the following to view your traces in the console.
```bash
bt view logs
```

## 4. Explore Topics on the shared seed

> **Note:** participants do not have access to the Braintrust UI, so this is instructor led.
```bash
bt topics open --project super-stonks
```

Target the **"Current stock price analysis"** cluster.

## 5. Investigate it with your coding agent

Ask your coding agent:
```text
How are traces performing in the "Current stock price analysis" topic cluster in 'super-stonks'? Pull a representative sample, compare what the user asked vs. how the agent responded.
```
Accept the dialogs while observing what Claude does to answer the question.

It should find the gap: price questions the agent can't answer — no realtime-price tool.

## 6. Curate the traces from the cluster into your dataset

Now, add 10 traces to a dataset in your own project for offline evaluation. Prompt your coding agent to do this.
```text
/agent-auto-improvement Capture 10 traces from the "Current stock price analysis" cluster as a dataset 'current-price-gap-offline' — the failure taxonomy/metadata is the price gap. Use /braintrust skill to capture traces and create a dataset.
```
As before, accept the dialogs while observing what Claude is doing.

Once the dataset is created, exit Claude with Ctrl + C, then view it with:
```bash
bt datasets view current-price-gap-offline
```

## 7. Select a scorer and push it to your project

Evals require at least one scorer. We've already defined the scorer in the code, and we can push scorers to our Braintrust project. This ensures versioned scorers are available across the team.
```bash
make push-scorer
```

Let's review the scorer we just pushed to our project. Select `response_grounded_in_data` when prompted.
```bash
bt scorers view
```

## 8. Baseline experiment (tool OFF)

`qa_eval.py` runs the agent over your dataset and scores each answer with the grounding
judge. Use the following command to run your eval.
```bash
EVAL_DATASET=current-price-gap-offline uv run bt eval src/super_stonks/evals/qa_eval.py
```

When the eval completes, view the results. Specifically, look for the scores from the scorer you just added, `response_grounded_in_data`.

## 9. Close the gap

The agent is missing a tool that can pull real-time stock prices from Yahoo Finance. We've already written this tool in the code, but it is currently disabled (commented out). `GAP.md` specifies exactly where to uncomment it so the tool is usable by the agent.

Start your coding agent again, then instruct it to do the following:
```text
Fill the tool gap @GAP.md.
```
When your coding agent is done, the tool should now be included in the agent's tools list. Exit with Ctrl + C.

Run the agent again, then generate fresh traffic by conversing with it:
```bash
make agent
```

When done, interrupt the agent with Ctrl + C, then view the interaction(s) in the console. Look specifically for the new tool spans.
```bash
bt view logs
```

## 10. A/B test the updated agent against the previous version

With the new tool available to the agent, run the eval experiment again.
```bash
EVAL_DATASET=current-price-gap-offline uv run bt eval src/super_stonks/evals/qa_eval.py
```

The new experiment should have a higher grounding score than the previous one. This is a good sign that the tool is working and the agent is able to use it.

## 11. Enable online scoring automation for the new scorer

Now we want to enable online scoring automation for the new scorer. This will automatically score new traces as they are logged to Braintrust, protecting us from regressions in the future.
```bash
make automations
```

## 12. Validate

Run the agent again to generate fresh traffic:
```bash
make agent
```

When done, interrupt the agent with Ctrl + C, then view the scoring added to the new trace in the logs:
```bash
bt view logs
```

Congratulations, you have just executed the Braintrust flywheel!