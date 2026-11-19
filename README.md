# TechTreks

Group-trip agent for a GroupMe chat: keeps track of the trip's plans, logs and splits expenses, and keeps everyone's budget on track. It doesn't suggest or look up places (decided Nov 12, 2026): the group decides what to do, and the bot keeps the calendar. Budgets are shared with everyone on the trip, and the bot only posts in the group. Design lives in [specs.md](specs.md) and [examples.md](examples.md).

## Agent (Phase 1–2)

```
agent/
  config.py                 model (qwen3.8-flash), thinking, endpoint
  prompts/system_prompt.md  system prompt v1
  tools/schemas.py          21 backend tools + set_payment_handle and send_message (runner-side)
  backend/protocol.py       the agent <-> backend contract
  backend/core/engine.py    TripEngine: every tool, run on trip_model objects (in memory for tests)
  backend/core/rules.py     placeholders: FX table (post-MVP)
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

Then type `priya: @tripbot I can't make it anymore`, or `mia: @tripbot lower my budget to $500`.

## CI

GitHub Actions (`.github/workflows/tests.yml`) runs on every PR and push to `main`:

- the offline Python tests
- the trip page's lint, tests and build

The live Qwen scenarios run only when started by hand: Actions → Tests → Run workflow → tick "live". They need the `DASHSCOPE_API_KEY` and `QWEN_BASE_URL` repo secrets.

## Agent evals

There are 36 scenarios: the 11 worked examples plus 25 edge cases (`tests/scenarios/edge_*.yaml`). The edge cases cover:

- prompt injection (fake approvals, impersonating the leader)
- staying quiet
- confirmations for edits, deletes and dropouts
- ambiguous expenses, foreign currency, slang and typos, corrections mid-thread
- multi-day settle-up
- polls, reminders and onboarding
- the trip's calendar: a plan with just a day, a named slot, a clock time, "are you sure?" for two plans at the same time, the ideas list, and where the group is staying
- saying no, in one line, to finding or planning places
- posting the trip page's link

```bash
.venv/bin/python scripts/eval_report.py              # live Qwen, every scenario 3 times
.venv/bin/python scripts/eval_report.py -k edge_     # just the edge cases
```

This writes [docs/eval-report.md](docs/eval-report.md): pass rate per scenario, what went wrong, and time and tokens per turn. Use `--out-dir` and `--report` to keep an experiment's transcripts and report apart from the main ones.

### Speed

Thinking is most of the reply time. After a model response that only sends messages, the next call (usually just "done", sometimes a remaining message) runs with thinking off. That cut a reply from about 25 s to about 11 s, at 97/99 on 33 scenarios × 3. Switches in `.env`:

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

- `POST /api/tools/<tool_name>`: any of the 26 tools, with the tool's arguments as the JSON body. Returns 400 `{"error": ...}` on bad input.
- `GET /api/trips/<id>/summary`: the state injected into each agent turn.
- `GET /api/trips/<id>` and `GET /api/trips/<id>/balances`: the full trip (money and budgets included) and balances.
- `GET /api/share/<share_token>`: what the trip page (`/t/<share_token>`) shows anyone with the link: the overview and itinerary, with no expenses, balances, budgets, group budget, payment handles or lodging (`trips/public.py`). Each trip gets a random 12-character `share_token`, so knowing a trip's id isn't enough.

The bot posts the trip page's link when someone asks for it. Set `TRIP_PAGE_URL` in `.env` to the website's address (default `http://localhost:3000`).

The agent talks to it with `agent/backend/http.py` (`HttpBackend`). See `.env.example` for the settings.

## GroupMe bot (Phase 4)

Django app `backend/bot`. GroupMe posts every group message to `/groupme/callback/<GROUPME_CALLBACK_SECRET>`. The bot:

- ignores bot and system messages and repeats;
- adds new senders to the trip;
- sends @mentions to the agent;
- posts group replies through the GroupMe bot API.

Every reply goes to the group. GroupMe bots can't send DMs, and budgets are shared with the trip, so there are no private messages. A reminder for some people tags them in the group.

Setup, once you have a GroupMe bot (dev.groupme.com/bots):

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py link_group <group_id> <bot_id> <trip_id> --name "Miami Spring Break"
```

Run `manage.py send_due_reminders` from cron every few minutes, or keep it running with `--every 60`. Times in chat are the group's local time, `BOT_TIME_ZONE` (default `America/New_York`): the bot tells the agent the local time with each message, and reminders fire on it.

The webhook answers GroupMe at once and queues the message. A worker thread per group runs the agent, one message at a time, so a chat's messages stay in order and its history isn't overwritten (`backend/bot/worker.py`). The queues live in one process, so run Django as a single process for now. Set `BOT_INLINE=1` to run the agent inside the request instead (the tests do).

Each reply sends only the last `AGENT_HISTORY_TURNS` messages (default 12), and only the newest carries the trip state, so a reply costs the same on day 5 as on day 1.

Testing without GroupMe: `scripts/webhook_smoke.py` posts a scripted 4-person chat to the real webhook on live Qwen, with a throwaway database, and prints what would be posted.

Testing with GroupMe from a laptop: `brew install cloudflared`, run Django, then `cloudflared tunnel --url http://127.0.0.1:8000`, and register `https://<tunnel host>/groupme/callback/<GROUPME_CALLBACK_SECRET>` as the bot's callback. Add `.trycloudflare.com` to `DJANGO_ALLOWED_HOSTS`. The tunnel URL changes on every restart.

People join the trip the first time they @mention the bot. Anyone can save their own payment handle ("@tripbot my venmo is @mia-v").

## Google sign-in (Phase 5)

Google-only sign-in through django-allauth. A signed-in person links themselves to their trip member by posting `@tripbot link <code>` in the group, After that, `GET /api/me/trips/<id>` returns the money side of the trip page (the full trip, balances and their own budget), and `GET /api/me/trips/<id>/budget` just their budget. Anyone else gets 401 (signed out) or 403 (not on the trip). Members can also act from the page: `POST /api/me/trips/<id>/payments` marks a payment they sent (up to what they owe that person; the same `request_id` twice records it once), `POST /api/me/trips/<id>/budget` changes their own total (category limits are kept), and `POST /api/me/trips/<id>/theme` picks the page's look. After a payment or a budget change the bot posts one short line in the group, like "Mia sent Aarav $25." Setup: [docs/google-signin.md](docs/google-signin.md).

## Trip page (Phase 5)

Next.js + Tailwind in `web/`. See [web/README.md](web/README.md). It reads fixtures by default, or the Django API when `TRIP_API_URL` is set.

## Placeholders

- FX: fixed rate table in `rules.py`. The provider is still TBD.
- Currency: the MVP is USD-only. The FX code keeps working but multi-currency is post-MVP.

## Planning: the trip's calendar

The bot keeps track of what the group decides and never suggests, looks up or checks places (Nov 12, 2026). There's no map service or places API.

- `add_activity`: "boat tour Saturday" is saved on that day with no time. It gets a slot (morning, lunch, afternoon, dinner, night) only when someone names one, and any number of plans can share a slot. A clock time ("Saturday 2pm") is saved as given. If another plan is at exactly that clock time, nothing is saved until the person says yes (`confirm_same_time`). Moving a plan to another day keeps its time or slot.
- `save_idea`: things the group wants to do without a day yet (up to 20). Putting one on a day takes it off the list, and removing that plan puts it back.
- `remove_activity`: right away, unless it's paid for or marked important.
- Where the group is staying (`lodging` on `update_trip`) is saved as the group wrote it. The trip page shows it to members with a Google Maps search link.
- The trip page's Maps buttons are plain Google Maps search links (Google's "Maps URLs": no key, no cost). Nobody checks they find the right place.
- Removed: itinerary drafts, destination suggestions, nearby search, travel-tip tiers, the map checks, and the Google Places and SerpAPI code. They're in git history if a good places API turns up.
