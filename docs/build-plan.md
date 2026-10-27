# Build plan and decisions

How the MVP is put together, the decisions behind it, and what's left. Design rules
live in [specs.md](../specs.md) and [examples.md](../examples.md); this file covers
the build. Last updated Oct 25, 2026.

## How the pieces fit

```
GroupMe group ──@tripbot──> Django /groupme/callback ──> agent (Qwen, tool calls)
                                    │                         │
                                    │                  DjangoBackend (tools, rules)
                                    │                         │
                       group reply / private notice      database (SQLite → Supabase)
                                                              │
Trip page (Next.js) ──/api/trips, /api/me (proxied)──> Django API
```

| Piece | Where | What it does |
|---|---|---|
| Agent | `agent/` | System prompt, 22 tools, Qwen tool-calling loop, CLI for a fake group chat |
| Data model | `trip_model/` | The trip's data and rules: splits, refunds, balances, settle-up, opt-outs, dropouts, polls, reminders, budgets |
| Engine | `agent/backend/core/` | `TripEngine`: every tool, run on `trip_model` objects; in memory for tests, and inside the Django backend |
| Backend | `backend/trips/` | Django models and `DjangoBackend`, which runs the same rules over the database; tool API |
| Bot | `backend/bot/` | GroupMe webhook, replies, private notices, reminders |
| Sign-in | `backend/accounts/` | Google sign-in, link code, "my budget" API |
| Trip page | `web/` | Itinerary, who owes whom, expenses, "My budget" |
| Tests | `tests/`, `web/__tests__/` | Each examples.md example replayed against the fake, the database and the API; bot, sign-in and page tests |

## Decisions log

| Date | Decision |
|---|---|
| Oct 20 | Payer doesn't have to be in the split (Example 7b) |
| Oct 22 | Agent gets a short trip summary every turn, plus a `get_trip` tool for details (20 backend tools) |
| Oct 22 | The agent only talks through `send_message` (group or one person), so private messages can't leak by accident |
| Oct 22 | Travel-tip tiers: 6 presets (0.5×, 0.75×, 1×, 1.25×, 1.5×, 2× of the group average) or any custom multiplier; anyone can propose, only the leader locks it in |
| Oct 22 | Budget warnings: placeholder "under 10% left" until the real rule is defined |
| Oct 22 | Exchange rates: fixed table until the provider is picked |
| Oct 22 | Model: Qwen with thinking on, Alibaba Cloud Model Studio (replaced the Claude API) |
| Oct 22 | Model is `qwen3.8-flash` (cheaper than max); the team key and endpoint are in the Singapore region, kept in the gitignored `.env` |
| Oct 27 | Adopted Roger's category-only budget warnings and greedy settle-up (one balance per person) |
| Oct 27 | The runner checks budgets for everyone affected after each expense, refund or dropout, and adds chat-ready amounts and settle-up lines to tool results (live runs showed the model skipping checks and misreading cents) |
| Oct 22 | Local database is SQLite; Supabase later by setting `DATABASE_URL` |
| Oct 22 | GroupMe DMs: test first with `scripts/groupme_dm_spike.py`. Until then, private messages are saved and shown on the trip page after sign-in |
| Oct 22 | Account linking works without DMs: sign in with Google, then post `@tripbot link <code>` in the group |
| Oct 22 | Each piece of work gets its own branch and PR, stacked so work doesn't wait on reviews |
| Oct 25 | `classes/` is the data model and money rules (later renamed `trip_model/`, see below) |
| Oct 25 | Expense splits are net changes per person (sum to 0); tool results also give each person's share |
| Oct 25 | Balances are netted across the group; the agent suggests payments (exact opposites first, then biggest debtor pays biggest creditor) |
| Oct 25 | Leftover cents go in id order instead of randomly |
| Oct 25 | Budget warnings: under 10% of a category limit left, counting planned activities; category limits only |
| Oct 25 | Percentage splits per expense (`percentages` on `log_expense`); new `record_payback` tool for real paybacks (21 backend tools) |
| Oct 25 | MVP is USD-only; multi-currency stays in the code but is post-MVP |
| Oct 25 | `trip_model/` (was `classes/`) is the only data model; the fake backend's dataclasses are gone, and it's renamed `agent/backend/core/` / `TripEngine` |
| Oct 25 | Each rule has one version, in `trip_model/` where it's a data rule |
| Oct 25 | Leader fields carried over unchanged while the team decides whether to keep the leader feature |

## Pull requests (stacked, merge in order)

1. `agent-harness`: agent, fake backend, tests from examples.md
2. `backend-api`: Django backend and tool API
3. `trip-page`: trip page on sample data
4. `groupme-bot`: GroupMe webhook, replies, reminders
5. `google-signin`: Google sign-in and private budget API
6. `trip-page-live`: trip page wired to the real API and sign-in
7. `project-docs`: this file and the updated project context

## Blocked / waiting on

- **Qwen access** (Alibaba account in verification): live agent tests (`pytest -m live`), prompt tuning, a real GroupMe demo.
- **GroupMe DM spike**: needs a GroupMe account and a teammate to receive a test DM.
- **Google OAuth client**: see [google-signin.md](google-signin.md).
- **Mentor**: demo date and what must work, exchange-rate provider.

## Next steps once Qwen works

1. Run `pytest -m live --repeat 3` and fix the prompt where scenarios fail (transcripts in `tests/out/`).
2. Create a GroupMe bot, run `manage.py link_group`, and try a real chat end to end.
3. Run the DM spike and choose the DM mode.
4. Deploy (backend + trip page on one domain, so sign-in works), and connect Supabase.
5. Swap placeholder travel tips and exchange rates for Google Places / SerpAPI and a real FX provider.
