# Tech Treks — Group Trip Agent: Project Context for Claude Code

> Started as a handoff from claude.ai planning chats (Oct 15–20, 2026); updated Oct 25, 2026.
> **Source of truth for design:** `specs.md` and `examples.md` in this repo. If anything here conflicts with those files, the files win. Build details and the decisions log: [docs/build-plan.md](docs/build-plan.md).

## 1. What we're building
An AI agent that lives in a group chat (GroupMe for now) and:
- plans a group trip (destination/date polls, itinerary),
- logs and splits group expenses from plain-text messages,
- gives travel tips by budget tier,
- tracks **per-person budgets** (shared with everyone on the trip) and warns people in the group before they overspend.

**Users:** college students, groups of 4–12, spring break / fall break / long weekends.
**Why:** customer discovery from Romir's finance startup (Quor) found students overspend on group trips → budgeting + privacy is the core hook, not just itinerary generation.
**Context:** Tech@NYU Tech Treks project. Name not picked yet (shortlist: Breakmate, Tripline, Squadtrip, Splitsville).

## 2. Team & ownership
| Who | Owns |
|---|---|
| **Romir** | Agent side — system prompt, tool definitions (specs.md), CoT examples (examples.md), eval harness/tests |
| **Shriya + Roger** | Backend API / web app, GroupMe bot integration |

First versions of the backend, bot, sign-in and trip page were built alongside the agent (PRs 2–6) so the whole flow could be tested end to end; they're ready for review.

Build order: **single-user first, multi-user later.**
Working style: Romir, Roger, and Shriya make the design decisions — when something is undecided, **ask, don't assume.**

## 3. Stack
- **Agent:** Qwen (`qwen3.8-flash`, thinking on) via Alibaba Cloud Model Studio's OpenAI-compatible API, Singapore region; key in the gitignored `.env`. Team decision Oct 22, 2026, replacing the Claude API
- **Chat:** GroupMe bot for MVP (Telegram considered; Sendblue/LoopMessage for iMessage later)
- **Backend:** Django (+ DRF)
- **DB:** Supabase Postgres (use as plain Postgres; don't use Supabase Auth to avoid two user systems). SQLite locally for now
- **Sign-in:** Google via django-allauth
- **Travel data:** Google Places + SerpAPI (Duffel only if in-app booking is added later)
- **Payments:** Venmo/Zelle deep links only (no money moves through us)
- **Currency:** the MVP is **USD-only**. Multi-currency (FX conversion, `convert_currency`, Example 6) stays in the code and keeps passing, but is post-MVP: no new work on it for now
- **Trip page:** Next.js + Tailwind

## 4. Data model
**`trip_model/` is the one data model** (decided Oct 25, 2026; it started as Roger's `classes/`). It holds the trip's data and its rules: splits, refunds, balances, settle-up, paybacks, dropouts, opt-outs, polls, reminders, budget warnings. `TripEngine` (`agent/backend/core/engine.py`) runs every tool on these objects; the Django backend loads a trip from the database into them and saves it back. Tests: `tests/test_trip_model.py`. Design notes: `trip_model/README.md`.

Category and TripStatus are Python enums in `trip_model/` (int values); tools, the database and the web page keep using the names (`"FOOD"`), converted at the edges (the engine and `backend/trips/services.py`), as are ISO strings ↔ dates/datetimes and person ids ↔ `Person` objects. The tool schemas take their category and status lists from the enums. All money in **cents**.

- **Person**: id, name, chat_user_id, payment_handle, budget (for this trip, shared with the trip), active (False after dropping out), trips
- **Budget**: owner_id, total_cents, limits {Category: cents}; `spent(category, expenses)` (their split share; SETTLEMENT never counts), `remaining(category, expenses)` (None if no limit), `warning(category, expenses, planned_cents)` = under 10% of that category's limit left, counting planned (unpaid) activities. Category limits only; the total doesn't warn
- **Expense**: id, paid_by, amount_cents, currency, original amount + base amount + FX rate, description, category, created_at, source_message
  - **splits {person_id: cents} are net changes, not shares**: + means owed money, − means owes; they sum to **0**. A person's share = what they paid − their split (`share_of(person_id)`)
  - `split_equal(ids)`, `split_custom({id: cents})` (covers the whole bill), `split_percentage({id: %})`
  - Leftover cents go to people in **id order** (equal split) or to the largest remainders (percentage split), so the same input always gives the same split
  - `original_amount`, `original_currency`, `fx_rate` are stored as typed in chat (post-MVP; USD and 1.0 for now)
- **Refund**: id, expense_id, amount_cents, per_person (same ratio as the shares), note, created_at. Made by `Expense.add_refund()`: can't exceed the expense, paybacks can't be refunded. Balances, spending and budgets take refunds off automatically
- **Opt-outs**: `Trip.opt_outs` {(person_id, Category)}; per-expense exclusions via `exclude[]` on `log_expense`. `Trip.split_people()` works out who's in an equal split (dropouts, exclusions, opt-outs, overrides)
- **Activity**: id, name, location?, start? (date or datetime), end?, est_cost_cents?, cost_is_per_person, attendees, important, booking_url?, expense_id; `est_per_person_cents()`; can't end before it starts
- **Poll**: id, question, options, votes {person_id: option}, closes_at, is_open; closes itself once `closes_at` passes; `vote()` checks the option; `winner()` returns every tied option
- **Reminder**: id, message, due_at, audience (list | "all"), sent, created_by ("agent" | "system"); `is_due()` (the bot uses it), `mark_sent()`
- **Trip**: id, name, status (PLANNING / BOOKED / ACTIVE / DONE), destination?, start_date?, end_date?, target_break?, base_currency, group_budget, members, activities, expenses, polls, reminders
  - stored settings: base_currency, group_budget, leader_id, leader_approval, auto_log_mode, itinerary_drafts. **The leader fields are carried over unchanged while the team decides whether to keep the leader feature**
  - methods: add_* (reject non-members and duplicate expense ids), get_member, remove_member, set/remove_opt_out, split_people, get/delete_expense, add_refund, itinerary_by_day (not used by the backend yet), spent_by_category
  - `summary()` → **the context contract fed to the agent each turn** lives in the engine, not the model
  - `balances()` → one net number per person (sums to 0)
  - `settlement_plan()` → suggested payments, **netted across the group**: exact opposites pay each other first, then the biggest debtor pays the biggest creditor. At most n − 1 payments; money only goes from people who owe to people who are owed. A suggestion only; it never changes balances
  - `record_settlement(from, to, amount_cents, payment_id)` → call only after a real payment; saved as a SETTLEMENT expense; the same payment_id can't be recorded twice
- **In the engine, not the model:** id generation, the leader/approval rules, travel tips and tier prices, itinerary drafts, FX conversion (post-MVP), `summary()`

## 5. Tools (21 + `send_message`) — the agent ↔ backend contract
Added since the first draft: `get_trip` (full trip state, including budgets), `send_message` (the agent's only way to talk: posts in the group) and `record_payback` (Oct 25). Current inputs are in `specs.md` and `agent/tools/schemas.py`.
"Confirm" = agent must get that confirmation in chat before calling.

**Expenses**
| Tool | Does | Confirm |
|---|---|---|
| `log_expense` | Log payment + splits; store original + base amount + rate; leftover cents in id order; apply exclusions/opt-outs. Equal split, exact amounts, or percentages of that expense. Returns each person's share and the net changes | No |
| `edit_expense` | Change amount/category/description/split | Payer |
| `delete_expense` | Remove wrongly logged expense | Payer |
| `record_refund` | Refund record; distributed back in the same ratio as the original shares | Yes |
| `record_payback` | A real off-app payment (Venmo, Zelle, cash), saved as SETTLEMENT; lowers what the sender owes | The payment happened |

**Trip & members**
| Tool | Does | Confirm |
|---|---|---|
| `add_member` | Add someone to trip | No |
| `remove_member` | Dropout: past splits stay (they still owe), removed from future splits/activities | Person + leader |
| `update_trip` | Destination, dates, base currency, status, target_break, group_budget | Yes (group) |
| `set_budget` | Person's total + category limits for this trip | No |
| `set_exclusion` | Blacklist: exclude from splits / opt out of a category | No |

**Planning**
| Tool | Does | Confirm |
|---|---|---|
| `generate_itinerary` | Day-by-day draft via Places/SerpAPI; post draft; save as Activities only after group confirms | Before saving |
| `add_activity` | Add/edit one activity | No |
| `get_travel_tips` | Tips across budget tiers from external APIs | No |
| `create_poll` | Group vote (destination, dates, activities) | No |
| `vote_poll` | Record votes from chat replies | No |
| `close_poll` | Close + return winner (applying it goes through `update_trip`, needs confirm) | No |

**Money info & other**
| Tool | Does | Confirm |
|---|---|---|
| `get_balances` | Net balance per person + suggested payments, netted across the group (group-visible) | No |
| `get_budget_status` | Person's remaining budget + warning check | No |
| `convert_currency` | Rate lookup / conversion | No |
| `create_reminder` | Schedule a reminder ("pay Airbnb by Friday") | No |

## 6. Agent behavior rules (decided)
- **Shared budgets (Oct 28, 2026):** everyone on the trip can see each person's budget, what's left and warnings. The bot only posts in the group and tags people with @Name. Only the person sets their own budget.
- **Budget = split share**, not what the person paid.
- **After every expense:** call `get_budget_status` for each person in the split; post any warnings in the group, tagging the person.
- **Default split:** if unclear who an expense is for, **ask** — never guess.
- **Rounding:** leftover cents go to people in the split in id order, so the same expense always splits the same way (changed Oct 25; was random).
- **Settling up:** balances are netted across the group and the agent suggests the fewest payments (changed Oct 25; was pair by pair). You may be told to pay someone other than the person who paid for your stuff.
- **Big changes** (dropout, destination/date/budget change, poll result applied) need confirmation; edits/deletes need the payer's confirmation.
- **Dropout:** needs both the person's and the leader's confirmation. Group gets the new per-person cost; the dropout is tagged with what they owe.
- **Exclusion conflict:** if someone opted out of a category but is explicitly named on an expense, ask before logging.
- **Currency (post-MVP; the MVP is USD-only):** ambiguous symbol (e.g. "$" abroad) → ask. Confirmations show both ("€90 (≈ $97)"). Settle up in payer's choice of currency; agent converts.
- **Travel tips:** 3 tiers (budget / mid / splurge) built from the group average; leader picks the tier; tips cover lodging, food, activities, money-saving. If someone's budget is below the chosen tier → say so in the group, kindly, and tag the leader.
- **Date change:** flag activities that fall outside the new dates; group decides. (See examples.md for location/budget-change handling.)
- **Travel info** comes from external APIs, not the model's own knowledge.
- **Listening:** reply only when @mentioned; may speak unprompted for important things only — budget warnings, conflicts, unpaid debts, deadlines.

## 7. Progress so far
- ✅ Concept, stack, data model, Trip object + methods designed
- ✅ `specs.md` and `examples.md` (plus Example 7b, payer outside the split; Example 5 rewritten for the 6-tier flow)
- ✅ Agent: system prompt v1, 21 backend tools + `send_message`, Qwen tool-calling loop, fake-chat CLI (`agent/`)
- ✅ Tests: every example replayed offline against the in-memory engine, the database and the API; live Qwen tests ready to run
- ✅ Django backend + tool API, GroupMe bot, Google sign-in, Next.js trip page (all tested offline)
- ✅ `trip_model/` (was `classes/`): the one data model and its rules, used by the whole backend (see §10)
- ✅ Examples 3 (running out of budget early) and 8 (overspend advice) drafted and in the test suite. Drafts: review welcome
- ⏳ Live Qwen runs and prompt tuning: waiting on Alibaba account verification
- ⏳ Not deployed yet; Supabase not connected
- The Oct 16 drafts (`schema.sql`, `examples.json`, etc.) were never in this repo and are superseded by the code above

## 8. Open questions (ask Romir, Roger or Shriya — don't decide)
- [x] **Budget warning logic** → under 10% of a category's limit left, counting planned (unpaid) activities; category limits only (`trip_model/budget.py`)
- [x] **Percentage splits** → `percentages{}` on `log_expense` / `edit_expense`, per expense
- [x] **Paybacks** → new `record_payback` tool; the backend makes the payment id (the bot already drops repeated GroupMe messages)
- [x] **Shares in results** → `log_expense`, `get_trip` and the trip summary return each person's share alongside the net-change `splits`
- [ ] FX rate provider (asking mentor; fixed table in use)
- [x] Can GroupMe DM people privately? → bots can't, and budgets are shared now (Oct 28), so the bot only posts in the group
- [ ] Mentor: demo date + what must work
- [x] Model + API key → Qwen `qwen3.8-flash` via Alibaba Cloud Model Studio (Singapore region); key in the gitignored `.env`
- [x] Trip state for the agent → injected summary every turn + `get_trip` tool
- [x] Travel-tip tiers → 6 presets (0.5×–2×) + custom multiplier; anyone proposes, leader confirms

## 9. What's next
1. When Qwen access works: `pytest -m live --repeat 3`, fix the prompt until the scenarios pass.
2. Real GroupMe test: create the bot, `manage.py link_group`, chat end to end.
3. Deploy the backend + trip page on one domain; connect Supabase; set up Google OAuth (`docs/google-signin.md`).
4. Replace placeholder travel tips / FX with Google Places, SerpAPI and a real FX provider.
5. Run the trip page tests (`cd web && npm install && npm test`); they weren't run after the Oct 25 changes.

## 10. Data model work (done Oct 25, 2026)
**Step 1: Roger's classes wired in.** The money rules started coming from the classes; behavior changes:

- **Splits** are net changes (sum to 0); every result that shows an expense also gives `shares`. Refunds go back by share and lower the payer's paid amount.
- **Balances:** `get_balances` returns `net_balances` and `suggested_payments` (netted, with handles). The scenario checker's `balance` checks read the suggested payments. Example 9 now settles as Mia → Jake $50.
- **Paybacks:** `record_payback`; `log_expense` and `edit_expense` refuse SETTLEMENT. Scenario seeds use `paybacks:`.
- **Rounding:** id order everywhere; the random seed is gone.
- **Budget warnings:** `trip_model/budget.py` rule; planned activities count.
- **Smaller rules:** activities can't end before they start; polls close themselves at `closes_at` (which must be ISO).
- **Agent text:** system prompt, tool descriptions, specs.md, examples.md, docs/build-plan.md decisions log.
- **Trip page:** `Expenses.tsx` uses `shares`, `Balances.tsx` shows suggested payments, types and fixtures updated. The web tests weren't run (see §9).

**Step 2: one data model, no repeated rules.** A refactor; tool results are unchanged except `created_at` dropping `:00` seconds.
- `classes/` → `trip_model/`, now the only data model: Refund, dropouts, opt-outs and `split_people`, optional Activity fields, Poll votes, Reminder ids and the trip settings moved in. The old dataclasses (`agent/backend/fake/models.py`) and the `ledger.py` bridge are gone.
- `agent/backend/fake/` → `agent/backend/core/`, `FakeBackend` → `TripEngine` (`engine.py`): it was never fake, the database runs the same code. `rules.py` keeps the placeholders (FX table, tier prices). Tests call the in-memory backend `"memory"`.
- One version of each rule: poll closing, voting and winners (`Poll`); activity times and per-person cost (`Activity`); "reminder is due" (`Reminder.is_due`, now used by `send_due_reminders`); spending by category (`trip_model.budget.spent`); payback and expense checks (`Trip`); proportional splits (`trip_model.money.split_proportional`, used by percentages, refunds and FX); category and status names (the enums, also used by the tool schemas). Model errors reach the agent as tool errors in one place.
- Kept on purpose: the trip page's own day grouping and category labels (display code). The leader approval-type list still appears in both the engine and the tool schema; left alone while the leader feature is undecided.
