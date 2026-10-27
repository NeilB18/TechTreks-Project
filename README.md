# TechTreks

Group-trip agent for a GroupMe chat: plans the trip, logs and splits expenses, gives travel tips by budget, and keeps private per-person budgets on track. Design lives in [specs.md](specs.md) and [examples.md](examples.md).

## Agent (Phase 1–2)

```
agent/
  config.py                 model (qwen3.8-flash), thinking, endpoint
  prompts/system_prompt.md  system prompt v1
  tools/schemas.py          21 backend tools + set_payment_handle and send_message (runner-side)
  backend/protocol.py       the agent <-> backend contract
  backend/core/engine.py    TripEngine: every tool, run on trip_model objects (in memory for tests)
  backend/core/rules.py     placeholders: FX table (post-MVP), tier prices
  runner.py                 Qwen function-calling loop for one chat message, plus guards (payer, refund
                            confirmation, budget numbers in the group, made-up members) and history trimming
  scenarios.py              runs + checks the examples.md scenarios
  cli.py                    fake multi-person chat
trip_model/                 the data model and its rules (splits, refunds, balances, settle-up, budgets, polls); see trip_model/README.md
tests/
  scenarios/*.yaml          one per example in examples.md
```

Setup:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Offline tests (no API key, free):

```bash
.venv/bin/pytest
```

Live tests against Qwen (costs credits; transcripts go to `tests/out/`). Put the key and endpoint in the gitignored `.env` (copy `.env.example`). The endpoint is your workspace's API Host from Model Studio → Workspace Management, plus `/compatible-mode/v1`. The key and endpoint must be from the same region (the team's is Singapore).

```bash
# .env: DASHSCOPE_API_KEY=...  QWEN_BASE_URL=https://<API Host>/compatible-mode/v1
.venv/bin/pytest -m live
.venv/bin/pytest -m live --repeat 3 -k ex7b
```

Chat with the agent by hand:

```bash
.venv/bin/python -m agent.cli tests/scenarios/ex1_dropout.yaml
```

Then type `priya: @tripbot I can't make it anymore`, or `mia dm: lower my budget to $500`.

## CI

GitHub Actions (`.github/workflows/tests.yml`) runs on every PR and push to `main`:

- the offline Python tests
- the trip page's lint, tests and build

The live Qwen scenarios run only when started by hand: Actions → Tests → Run workflow → tick "live". They need the `DASHSCOPE_API_KEY` and `QWEN_BASE_URL` repo secrets.

## Agent evals

There are 34 scenarios: the 12 worked examples plus 22 edge cases (`tests/scenarios/edge_*.yaml`). The edge cases cover:

- privacy probes and prompt injection (budget dumps, fake approvals, impersonating the leader), and setting a budget in the group
- staying quiet
- confirmations for edits, deletes, itinerary saves and dropouts
- ambiguous expenses, foreign currency, slang and typos, corrections mid-thread
- multi-day settle-up
- polls, reminders and onboarding

```bash
.venv/bin/python scripts/eval_report.py              # live Qwen, every scenario 3 times
.venv/bin/python scripts/eval_report.py -k edge_     # just the edge cases
```

This writes [docs/eval-report.md](docs/eval-report.md): pass rate per scenario, what went wrong, and time and tokens per turn. Use `--out-dir` and `--report` to keep an experiment's transcripts and report apart from the main ones.

### Speed

Thinking is most of the reply time. After a model response that only sends messages, the next call (usually just "done", sometimes the remaining DMs) runs with thinking off. That cut a reply from about 25 s to about 11 s, at 97/99 on 33 scenarios × 3. Switches in `.env`:

- `QWEN_THINKING=0` turns thinking off everywhere (about 5 s per reply, but only 79% pass)
- `QWEN_THINKING_BUDGET=<tokens>` caps thinking
- `QWEN_FAST_FOLLOWUP=0` keeps thinking on for the follow-up call

## Demo

```bash
.venv/bin/python scripts/demo.py   # a scripted 4-person chat on live Qwen, about 2 minutes
```

It writes [docs/demo-transcript.md](docs/demo-transcript.md). Talking points are in [docs/demo-guide.md](docs/demo-guide.md).

## Backend (Phase 3)

Django + DRF in `backend/`, SQLite locally (set `DATABASE_URL` for Supabase Postgres later).
`trips/services.py` (`DjangoBackend`) loads a trip from the database into `trip_model` objects, runs the same `TripEngine`,
so the examples.md replays pass against the fake, the database, and the HTTP API.

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver
```

API (all routes need `Authorization: Bearer $AGENT_API_TOKEN`; the dev default is `dev-agent-token`):

- `POST /api/tools/<tool_name>`: any of the 21 tools, with the tool's arguments as the JSON body. Returns 400 `{"error": ...}` on bad input.
- `GET /api/trips/<id>/summary`: the state injected into each agent turn.
- `GET /api/trips/<id>` and `GET /api/trips/<id>/balances`: for the trip page. These never include budgets.

The agent talks to it with `agent/backend/http.py` (`HttpBackend`). See `.env.example` for the settings.

## GroupMe bot (Phase 4)

Django app `backend/bot`. GroupMe posts every group message to `/groupme/callback/<GROUPME_CALLBACK_SECRET>`. The bot:

- ignores bot and system messages and repeats;
- adds new senders to the trip;
- sends @mentions to the agent;
- posts group replies through the GroupMe bot API.

Private messages (budgets) never go to the group. Until DMs are confirmed, they're saved as private notices for the trip page (`BOT_DM_MODE=store`).

Setup, once you have a GroupMe bot (dev.groupme.com/bots):

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py link_group <group_id> <bot_id> <trip_id> --name "Miami Spring Break"
```

Run `manage.py send_due_reminders` from cron every few minutes, or keep it running with `--every 60`. Times in chat are the group's local time, `BOT_TIME_ZONE` (default `America/New_York`): the bot tells the agent the local time with each message, and reminders fire on it.

The webhook answers GroupMe at once and queues the message. A worker thread per group runs the agent, one message at a time, so a chat's messages stay in order and its history isn't overwritten (`backend/bot/worker.py`). The queues live in one process, so run Django as a single process for now. Set `BOT_INLINE=1` to run the agent inside the request instead (the tests do).

Each reply sends only the last `AGENT_HISTORY_TURNS` messages (default 12), and only the newest carries the trip state, so a reply costs the same on day 5 as on day 1.

Testing without GroupMe: `scripts/webhook_smoke.py` posts a scripted 4-person chat to the real webhook on live Qwen, with a throwaway database, and prints what would be posted and stored privately. Read stored private messages with `manage.py show_notices <trip_id> [--person <id>]`.

Testing with GroupMe from a laptop: `brew install cloudflared`, run Django, then `cloudflared tunnel --url http://127.0.0.1:8000`, and register `https://<tunnel host>/groupme/callback/<GROUPME_CALLBACK_SECRET>` as the bot's callback. Add `.trycloudflare.com` to `DJANGO_ALLOWED_HOSTS`. The tunnel URL changes on every restart.

People join the trip the first time they @mention the bot. Anyone can save their own payment handle ("@tripbot my venmo is @mia-v").

DM check: `GROUPME_ACCESS_TOKEN=... .venv/bin/python scripts/groupme_dm_spike.py <recipient_user_id>`. GroupMe bots can't DM, so this tests DMs sent from a user account.

## Google sign-in (Phase 5)

Google-only sign-in through django-allauth. A signed-in person links themselves to their trip member by posting `@tripbot link <code>` in the group, so no DMs are needed. After that, `GET /api/me/trips/<id>/budget` returns their own budget and nobody else's. Setup: [docs/google-signin.md](docs/google-signin.md).

## Trip page (Phase 5)

Next.js + Tailwind in `web/`. See [web/README.md](web/README.md). It reads fixtures by default, or the Django API when `TRIP_API_URL` is set.

## Placeholders

- FX: fixed rate table in `rules.py`. The provider is still TBD.
- Travel tips and itineraries use built-in sample data until keys are added. With `GOOGLE_PLACES_API_KEY` in `.env`, they come from Google Places: real restaurants and attractions, ratings, and price levels matched to the tier. Adding `SERPAPI_KEY` also brings in real hotel prices from Google Hotels, capped at about 40% of the tier's budget for a shared room. If an API call fails, the tool falls back to sample data with a note. Tests and evals always use the sample data. Note: Places fields like rating and price level bill at Google's Enterprise rate.
- Currency: the MVP is USD-only. The FX code keeps working but multi-currency is post-MVP.
