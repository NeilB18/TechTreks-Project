# TechTreks

Group-trip agent for a GroupMe chat: plans the trip, logs and splits expenses, gives travel tips by budget, and keeps private per-person budgets on track. Design lives in [specs.md](specs.md) and [examples.md](examples.md).

## Agent (Phase 1–2)

```
agent/
  config.py                 model (qwen3.8-flash), thinking, endpoint
  prompts/system_prompt.md  system prompt v1
  tools/schemas.py          20 backend tools + send_message
  backend/protocol.py       the agent <-> backend contract
  backend/fake/             in-memory data model + FakeBackend (placeholder rules in rules.py)
  runner.py                 Qwen function-calling loop for one chat message
  scenarios.py              runs + checks the examples.md scenarios
  cli.py                    fake multi-person chat
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

Live tests against Qwen (costs credits; transcripts go to `tests/out/`). The key and endpoint go in the gitignored `.env` (copy `.env.example`); the endpoint is your workspace's API Host from Model Studio (Workspace Management) plus `/compatible-mode/v1`:

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

## Agent evals

There are 27 scenarios: the 12 worked examples plus 15 edge cases (`tests/scenarios/edge_*.yaml`). The edge cases cover:

- privacy probes
- staying quiet
- confirmations for edits, deletes, itinerary saves and dropouts
- ambiguous expenses and foreign currency
- polls, reminders and onboarding

```bash
.venv/bin/python scripts/eval_report.py              # live Qwen, every scenario 3 times
.venv/bin/python scripts/eval_report.py -k edge_     # just the edge cases
```

This writes [docs/eval-report.md](docs/eval-report.md): pass rate per scenario, what went wrong, and time and tokens per turn.

## Backend (Phase 3)

Django + DRF in `backend/`, SQLite locally (set `DATABASE_URL` for Supabase Postgres later).
`trips/services.py` (`DjangoBackend`) runs the same rules as the fake backend over the database,
so the examples.md replays pass against the fake, the database, and the HTTP API.

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver
```

API (all routes need `Authorization: Bearer $AGENT_API_TOKEN`; the dev default is `dev-agent-token`):

- `POST /api/tools/<tool_name>`: any of the 20 tools, with the tool's arguments as the JSON body. Returns 400 `{"error": ...}` on bad input.
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

Run `manage.py send_due_reminders` from cron every few minutes.

DM check: `GROUPME_ACCESS_TOKEN=... .venv/bin/python scripts/groupme_dm_spike.py <recipient_user_id>`. GroupMe bots can't DM, so this tests DMs sent from a user account.

## Google sign-in (Phase 5)

Google-only sign-in through django-allauth. A signed-in person links themselves to their trip member by posting `@tripbot link <code>` in the group, so no DMs are needed. After that, `GET /api/me/trips/<id>/budget` returns their own budget and nobody else's. Setup: [docs/google-signin.md](docs/google-signin.md).

## Trip page (Phase 5)

Next.js + Tailwind in `web/`. See [web/README.md](web/README.md). It reads fixtures by default, or the Django API when `TRIP_API_URL` is set.

## CI

GitHub Actions (`.github/workflows/tests.yml`) runs on every PR and push to `main`:

- the offline Python tests
- the trip page's lint, tests and build

The live Qwen scenarios run only when started by hand: Actions → Tests → Run workflow → tick "live". They need the `DASHSCOPE_API_KEY` and `QWEN_BASE_URL` repo secrets.

## Placeholders

- FX: fixed rate table in `rules.py`. The provider is still TBD.
- Travel tips and itineraries use built-in sample data until keys are added. With `GOOGLE_PLACES_API_KEY` in `.env`, they come from Google Places: real restaurants and attractions, ratings, and price levels matched to the tier. Adding `SERPAPI_KEY` also brings in real hotel prices from Google Hotels, capped at about 40% of the tier's budget for a shared room. If an API call fails, the tool falls back to sample data with a note. Tests and evals always use the sample data. Note: Places fields like rating and price level bill at Google's Enterprise rate.
