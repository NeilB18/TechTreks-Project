# Tech Treks — Group Trip Agent: Project Context for Claude Code

> Started as a handoff from claude.ai planning chats (Oct 15–20, 2026); updated Oct 25, 2026.
> **Source of truth for design:** `specs.md` and `examples.md` in this repo. If anything here conflicts with those files, the files win. Build details and the decisions log: [docs/build-plan.md](docs/build-plan.md).

## 1. What we're building
An AI agent that lives in a group chat (GroupMe for now) and:
- plans a group trip (destination/date polls, itinerary),
- logs and splits group expenses from plain-text messages,
- gives travel tips by budget tier,
- tracks **private per-person budgets** and warns people (by DM) before they overspend.

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
- **Agent:** Qwen (`qwen3.8-max`, thinking on) via Alibaba Cloud Model Studio's OpenAI-compatible API, US (Virginia) region. Team decision Oct 22, 2026, replacing the Claude API
- **Chat:** GroupMe bot for MVP (Telegram considered; Sendblue/LoopMessage for iMessage later)
- **Backend:** Django (+ DRF)
- **DB:** Supabase Postgres (use as plain Postgres; don't use Supabase Auth to avoid two user systems). SQLite locally for now
- **Sign-in:** Google via django-allauth
- **Travel data:** Google Places + SerpAPI (Duffel only if in-app booking is added later)
- **Payments:** Venmo/Zelle deep links only (no money moves through us)
- **Trip page:** Next.js + Tailwind

## 4. Data model
**`classes/` is the data model and money rules** (decided Oct 25, 2026). The backend uses it through `agent/backend/fake/ledger.py`: the fake backend's dataclasses stay the storage shape (the database mirrors them), and the rules (splits, balances, settle-up, paybacks, budget warnings) come from `classes/`. Tests: `tests/test_classes.py`. Design notes: `classes/README.md`.

Category and TripStatus are Python enums in `classes/` (int values); tools, the database and the web page keep using the names (`"FOOD"`), converted at the edges. All money in **cents**.

- **Person**: id, name, chat_user_id, payment_handle, budget (private), trips
- **Budget**: owner_id, total_cents, limits {Category: cents}; `spent(category, expenses)` (their split share; SETTLEMENT never counts), `remaining(category, expenses)` (None if no limit), `warning(category, expenses, planned_cents)` = under 10% of that category's limit left, counting planned (unpaid) activities. Category limits only; the total doesn't warn
- **Expense**: id, paid_by, amount_cents, currency, original amount + base amount + FX rate, description, category, created_at, source_message
  - **splits {person_id: cents} are net changes, not shares**: + means owed money, − means owes; they sum to **0**. A person's share = what they paid − their split (`share_of(person_id)`)
  - `split_equal(ids)`, `split_custom({id: cents})` (covers the whole bill), `split_percentage({id: %})`
  - Leftover cents go to people in **id order** (equal split) or to the largest remainders (percentage split), so the same input always gives the same split
- **Refund**: separate record against an expense
- **Exclusion**: (person_id, category) category opt-outs; per-expense exclusions via `exclude[]` on `log_expense`
- **Activity**: id, name, location, start, end, est_cost_cents, cost_is_per_person, attendees, important, booking_url, expense_id
- **Poll**: id, question, options, votes {person_id: option}, closes_at, is_open; closes itself once `closes_at` passes; `winner()` returns every tied option
- **Reminder**: message, due_at, audience (list | "all"), sent, created_by ("agent" | "system"); `is_due()`, `mark_sent()`
- **Trip**: id, name, status (PLANNING / BOOKED / ACTIVE / DONE), destination?, start_date?, end_date?, target_break?, base_currency, group_budget, members, activities, expenses, polls, reminders
  - methods: add_* (reject non-members and duplicate expense ids), itinerary_by_day, spent_by_category, `summary()` → **the context contract fed to the agent each turn** (align with Shriya/Roger)
  - `balances()` → one net number per person (sums to 0)
  - `settlement_plan()` → suggested payments, **netted across the group**: exact opposites pay each other first, then the biggest debtor pays the biggest creditor. At most n − 1 payments; money only goes from people who owe to people who are owed. A suggestion only; it never changes balances
  - `record_settlement(from, to, amount_cents, payment_id)` → call only after a real payment; saved as a SETTLEMENT expense; the same payment_id can't be recorded twice
- **Not in `classes/`** (handled in `agent/backend/fake/`): currency fields, Refund, category opt-outs, dropouts (`active`), leader / leader_approval / group_budget / auto_log_mode, itinerary drafts, `summary()`

## 5. Tools (21 + `send_message`) — the agent ↔ backend contract
Added since the first draft: `get_trip` (full trip state, never budgets), `send_message` (the agent's only way to talk: the group, or one person privately) and `record_payback` (Oct 25). Current inputs are in `specs.md` and `agent/tools/schemas.py`.
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
| `set_budget` | Person's private total + category limits (DM only) | No |
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
| `get_budget_status` | Person's remaining budget + warning check (DM only) | No |
| `convert_currency` | Rate lookup / conversion | No |
| `create_reminder` | Schedule a reminder ("pay Airbnb by Friday") | No |

## 6. Agent behavior rules (decided)
- **Privacy:** individual budgets never appear in the group; budget info is DM-only. Group may see the group **average** only.
- **Budget = split share**, not what the person paid.
- **After every expense:** call `get_budget_status` for each person in the split; DM any warnings.
- **Default split:** if unclear who an expense is for, **ask** — never guess.
- **Rounding:** leftover cents go to people in the split in id order, so the same expense always splits the same way (changed Oct 25; was random).
- **Settling up:** balances are netted across the group and the agent suggests the fewest payments (changed Oct 25; was pair by pair). You may be told to pay someone other than the person who paid for your stuff.
- **Big changes** (dropout, destination/date/budget change, poll result applied) need confirmation; edits/deletes need the payer's confirmation.
- **Dropout:** needs both the person's and the leader's confirmation. Group gets the new per-person cost; the dropout gets a DM with what they owe.
- **Exclusion conflict:** if someone opted out of a category but is explicitly named on an expense, ask before logging.
- **Currency:** ambiguous symbol (e.g. "$" abroad) → ask. Confirmations show both ("€90 (≈ $97)"). Settle up in payer's choice of currency; agent converts.
- **Travel tips:** 3 tiers (budget / mid / splurge) built from the group average; leader picks the tier; tips cover lodging, food, activities, money-saving. If someone's budget is below the chosen tier → DM them + DM the leader naming them.
- **Date change:** flag activities that fall outside the new dates; group decides. (See examples.md for location/budget-change handling.)
- **Travel info** comes from external APIs, not the model's own knowledge.
- **Listening:** reply only when @mentioned; may speak unprompted for important things only — budget warnings, conflicts, unpaid debts, deadlines.

## 7. Progress so far
- ✅ Concept, stack, data model, Trip object + methods designed
- ✅ `specs.md` and `examples.md` (plus Example 7b, payer outside the split; Example 5 rewritten for the 6-tier flow)
- ✅ Agent: system prompt v1, 21 backend tools + `send_message`, Qwen tool-calling loop, fake-chat CLI (`agent/`)
- ✅ Tests: every example replayed offline against the fake backend, the database and the API; live Qwen tests ready to run
- ✅ Django backend + tool API, GroupMe bot, Google sign-in, Next.js trip page (all tested offline)
- ✅ `classes/`: data model + money rules (splits, net balances, settlement plan, paybacks, budget warnings), wired into the backend Oct 25 (see §10)
- ✅ Examples 3 (running out of budget early) and 8 (overspend advice) drafted and in the test suite. Drafts: review welcome
- ⏳ Live Qwen runs and prompt tuning: waiting on Alibaba account verification
- ⏳ Not deployed yet; Supabase not connected
- The Oct 16 drafts (`schema.sql`, `examples.json`, etc.) were never in this repo and are superseded by the code above

## 8. Open questions (ask Romir, Roger or Shriya — don't decide)
- [x] **Budget warning logic** → under 10% of a category's limit left, counting planned (unpaid) activities; category limits only (`classes/budget.py`)
- [x] **Percentage splits** → `percentages{}` on `log_expense` / `edit_expense`, per expense
- [x] **Paybacks** → new `record_payback` tool; the backend makes the payment id (the bot already drops repeated GroupMe messages)
- [x] **Shares in results** → `log_expense`, `get_trip` and the trip summary return each person's share alongside the net-change `splits`
- [ ] FX rate provider (asking mentor; fixed table in use)
- [ ] Can GroupMe DM people privately? Run `scripts/groupme_dm_spike.py`. Until then, private messages are saved and shown on the trip page after sign-in
- [ ] Mentor: demo date + what must work
- [x] Model + API key → Qwen `qwen3.8-max` via Alibaba Cloud Model Studio (US region); account in verification
- [x] Trip state for the agent → injected summary every turn + `get_trip` tool
- [x] Travel-tip tiers → 6 presets (0.5×–2×) + custom multiplier; anyone proposes, leader confirms

## 9. What's next
1. When Qwen access works: `pytest -m live --repeat 3`, fix the prompt until the scenarios pass.
2. Real GroupMe test: create the bot, `manage.py link_group`, chat end to end.
3. Deploy the backend + trip page on one domain; connect Supabase; set up Google OAuth (`docs/google-signin.md`).
4. Replace placeholder travel tips / FX with Google Places, SerpAPI and a real FX provider.
5. Run the trip page tests (`cd web && npm install && npm test`); they weren't run after the Oct 25 changes.

## 10. `classes/` wiring (done Oct 25, 2026)
The Django backend runs the fake backend's logic on every tool call (`backend/trips/services.py`), so the classes plug into `agent/backend/fake/` through `ledger.py` and reach the database, API and trip page from there. No database schema change: `ExpenseSplit.cents` now holds net changes.

- **Splits** are net changes (sum to 0); every result that shows an expense also gives `shares`. Refunds go back by share and lower the payer's paid amount.
- **Balances:** `get_balances` returns `net_balances` and `suggested_payments` (netted, with handles). The scenario checker's `balance` checks read the suggested payments. Example 9 now settles as Mia → Jake $50.
- **Paybacks:** `record_payback`; `log_expense` and `edit_expense` refuse SETTLEMENT. Scenario seeds use `paybacks:`.
- **Rounding:** id order everywhere; the random seed is gone.
- **Budget warnings:** `classes/budget.py` rule; planned activities count.
- **Smaller rules:** activities can't end before they start; polls close themselves at `closes_at` (which must be ISO).
- **Agent text:** system prompt, tool descriptions, specs.md, examples.md, docs/build-plan.md decisions log.
- **Trip page:** `Expenses.tsx` uses `shares`, `Balances.tsx` shows suggested payments, types and fixtures updated. The web tests weren't run (see §9).
