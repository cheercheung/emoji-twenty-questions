# Emoji Twenty Questions (twenty cool calls)

**English** | [简体中文](README.zh-CN.md)

A hidden emoji, 20 turns, and only yes/no answers. One LLM (the **Guess** model) asks questions and makes guesses; a second LLM (the **Judge** model) knows the answer and replies with nothing but YES or NO. Every game shows the full question log with per-call time, tokens and real cost, so you can compare how well different models narrow things down.

All models (Claude and GPT) are reached through the [EvoLink](https://evolink.ai) gateway, so a single API key is all you need. The full specification is in [spec.md](spec.md) (Chinese).

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or plain `pip`
- An EvoLink account with some credits

## Quick start

### 1. Get an EvoLink API key

1. Open <https://evolink.ai/dashboard/keys> and sign in (register first if you have no account).
2. Create a new API key and copy it. It usually starts with `sk-`.

### 2. Put the key in the environment file

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder:

```dotenv
EVOLINK_API_KEY=sk-your-real-key
```

`.env` is listed in `.gitignore`. Never commit it or share the key.

### 3. Install and run

With uv:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Or with pip:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

### 4. Play

Open <http://127.0.0.1:8000>.

1. Pick the **Guess** model, the **Judge** model, and the hidden emoji (leave it empty for a random one).
2. Click start. The game runs by itself, one turn at a time.
3. Use the 中文 / English switch in the top right corner. It changes both the interface and the language the model asks its questions in.

The result card shows:

- The Guess and Judge models side by side at the top
- The question log: action, content, Yes / No, Guess time, Judge time, total
- An overview with three rows (Guess, Judge, Total): calls, time, tokens, cost

If a model call fails, the game stops in an error state and you can click retry to continue the same game.

## Set it up with an AI agent

If you use a coding agent (Claude Code, Cursor, Codex and so on), open this folder in it and paste the prompt below. The agent installs everything, opens the browser so you can sign in and get the key, writes the key to `.env`, and starts the app.

```text
Set up and run this project for me. Follow these steps in order.

1. Read README.md and .env.example to understand the project.

2. If .env does not exist, create it by copying .env.example.
   If .env already contains a real EVOLINK_API_KEY (not empty and not
   "your_key_here"), skip to step 5.

3. Open https://evolink.ai/dashboard/keys in a browser.
   - If you have a browser tool, use it. Otherwise run the system command
     (macOS: open <url>, Linux: xdg-open <url>, Windows: start <url>).
   - If the page asks for a login, stop and wait for me to sign in or
     register myself. Do not type my password or any login credential.
   - When I am signed in, create a new API key on that page (name it
     "emoji-twenty-questions") and copy it. If you cannot read or control
     the page, ask me to create the key and paste it to you.

4. Write the key into .env as the value of EVOLINK_API_KEY, replacing the
   placeholder. Change nothing else in the file. Do not print the key in
   chat, logs or command output, do not write it to any other file, and
   never commit .env.

5. Install dependencies and start the server:
     uv sync
     uv run uvicorn app.main:app --reload
   If uv is not installed, use:
     python3.11 -m venv .venv
     .venv/bin/pip install -r requirements.txt
     .venv/bin/uvicorn app.main:app --reload
   Run the server in the background so it keeps running.

6. Check the setup:
     curl -s http://127.0.0.1:8000/api/models
   "apiKeyConfigured" must be true. This only proves the key is not empty,
   so also start one real game to prove the key works:
     curl -s -X POST http://127.0.0.1:8000/api/games \
       -H 'Content-Type: application/json' \
       -d '{"model":"claude-sonnet-5-5","mode":"auto"}'
   If the response has "status":"error", show me the "error" text and fix
   the cause (wrong key, no credits, network) before continuing.

7. Open http://127.0.0.1:8000 in the browser and tell me it is ready.
```

## Batch runs from the command line

Run many games per model and get win rates:

```bash
uv run python scripts/run_batch.py --models claude-opus-5-5 gpt-6.1-sol --games 10
```

| Option | Default | Meaning |
|---|---|---|
| `--models` | all registered models | Guess model IDs to test |
| `--games` | `5` | Games per model |
| `--judge` | `JUDGE_MODEL` | Judge model ID |
| `--concurrency` | `3` | Games running at the same time |

The script prints wins, losses, errors, win rate and average turns per model, and writes the full result to `results/batch-<timestamp>.json`.

## Environment variables

Only `EVOLINK_API_KEY` is required. Restart the server after changing `.env`. Each variable is explained in detail in [.env.example](.env.example).

| Variable | Default | Meaning |
|---|---|---|
| `EVOLINK_API_KEY` | required | EvoLink key from <https://evolink.ai/dashboard/keys> |
| `EVOLINK_BASE_URL` | `https://direct.evolink.ai` | Gateway address. Use `https://api.evolink.ai` if the default line is unreachable |
| `JUDGE_MODEL` | `claude-sonnet-5-5` | Default Judge model. The page dropdown overrides it |
| `QUESTION_LANGUAGE` | `中文` | Question language for the batch script. The page uses its own language switch |
| `MAX_TURNS` | `20` | Turn limit per game |
| `LLM_TIMEOUT` | `120` | Timeout of one model call, in seconds |
| `EVOLINK_CREDIT_USD` | `0.0147` | US dollars per EvoLink credit, used to convert cost |

## Models

| ID | Name | Interface |
|---|---|---|
| `claude-opus-5-5` | Claude Opus 5.5 | `POST /v1/messages` |
| `claude-sonnet-5-5` | Claude Sonnet 5.5 | `POST /v1/messages` |
| `claude-fable-5-1` | Claude Fable 5.1 | `POST /v1/messages` |
| `gpt-6.1-sol` | GPT-6.1 Sol | `POST /v1/chat/completions` |
| `gpt-6-astra` | GPT-6 Astra | `POST /v1/chat/completions` |

To add or remove a model, edit the `MODELS` list in [app/config.py](app/config.py). The `provider` field selects the interface: `anthropic` uses forced tool calling to get strict JSON, `openai` uses `response_format=json_schema`. If the gateway rejects the structured-output parameters, the app falls back to plain text and extracts the JSON.

## Rules enforced by the backend

1. **Turn limit.** Every ask and every guess costs one turn. On the last turn the model is told it must guess. After 20 turns without a correct guess the game is lost.
2. **Answer isolation.** The Guess model's prompt never contains the hidden emoji, and the API does not return it while a game is in progress. Only the Judge sees the answer and the current question.

The hidden emoji comes from a curated set of 111 clearly distinct emoji in [app/emojis.py](app/emojis.py). A guess outside that set counts as wrong.

## How cost is measured

Cost is the real EvoLink charge: the app reads `/v1/credits` before and after each call and takes the difference, then converts credits to dollars with `EVOLINK_CREDIT_USD`. In batch runs the calls overlap and a charge cannot be assigned to a single call, so the app estimates cost from the per-token prices in [app/config.py](app/config.py) instead.

## Project layout

```
app/main.py      FastAPI routes
app/game.py      Game state and rule enforcement
app/guesser.py   Prompt for the Guess model (never contains the answer)
app/judge.py     Prompt for the Judge model
app/llm.py       EvoLink client for Claude and GPT interfaces
app/batch.py     Batch runs and statistics
app/emojis.py    Candidate emoji set
app/config.py    Environment variables and model registry
static/          Web page (plain HTML, CSS, JS)
scripts/         Command-line batch script
```

Game state lives in memory, so games are lost when the server restarts.

## Troubleshooting

| Problem | What to do |
|---|---|
| Banner at the top of the page says the key is missing | `EVOLINK_API_KEY` is empty in `.env`. Fill it in and restart the server |
| Game stops with an authentication error | The key is wrong, revoked, or still the placeholder. Create a new one at <https://evolink.ai/dashboard/keys> |
| Game stops with a balance or quota error | Top up credits in the EvoLink dashboard |
| Timeouts or connection errors | Set `EVOLINK_BASE_URL=https://api.evolink.ai`, or raise `LLM_TIMEOUT` |
| Changes to `.env` have no effect | Restart the server. `--reload` only watches code files |
| On macOS with a system proxy | Requests to the gateway go through the proxy. Requests to `127.0.0.1` and `localhost` connect directly, so a local mock gateway still works |
