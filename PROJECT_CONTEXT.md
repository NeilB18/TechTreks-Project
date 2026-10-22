# Tech Treks — Group Trip Agent: Project Context for Claude Code

> Started as a handoff from claude.ai planning chats (Oct 15–20, 2026); updated Oct 22, 2026.
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
Working style: Romir makes the design decisions — when something is undecided, **ask, don't assume.**

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
Category enum: `LODGING, TRANSPORT, FOOD, DRINKS, ACTIVITIES, OTHER, SETTLEMENT`. All money in **cents**.

- **Person**: id, name, chat_user_id, payment_handle, budget (private), trips
- **Budget**: owner_id, total_cents, limits {Category: cents}; remaining(category, expenses)
- **Expense**: id, paid_by, amount_cents, currency, original amount + base amount + FX rate, description, category, splits {person_id: cents} (must sum to amount), created_at, source_message
- **Refund**: separate record against an expense
- **Exclusion**: (person_id, category) category opt-outs; per-expense exclusions via `exclude[]` on `log_expense`
- **Activity**: id, name, location, start, end, est_cost_cents, cost_is_per_person, attendees, important, booking_url, expense_id
- **Poll**: id, question, options, votes {person_id: option}, closes_at, is_open
- **Reminder**: message, due_at, audience (list | "all"), sent, created_by ("agent" | "system")
- **Trip**: id, name, status (PLANNING / BOOKED / ACTIVE / DONE), destination?, start_date?, end_date?, target_break?, base_currency, group_budget, members, activities, expenses, polls, reminders
  - methods: add_*, itinerary_by_day, spent_by_category, balances, `summary()` → **the context contract fed to the agent each turn** (align with Shriya/Roger)

## 5. Tools (20 + `send_message`) — the agent ↔ backend contract
Added since the first draft: `get_trip` (full trip state, never budgets) and `send_message` (the agent's only way to talk: the group, or one person privately). Current inputs are in `specs.md` and `agent/tools/schemas.py`.
"Confirm" = agent must get that confirmation in chat before calling.

**Expenses**
| Tool | Does | Confirm |
|---|---|---|
| `log_expense` | Log payment + splits; store original + base amount + rate; random leftover cent; apply exclusions/opt-outs. Supports equal split and exact amounts | No |
| `edit_expense` | Change amount/category/description/split | Payer |
| `delete_expense` | Remove wrongly logged expense | Payer |
| `record_refund` | Refund record; distributed back in the same ratio as the original split | Yes |

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
| `get_balances` | Who owes whom (group-visible) | No |
| `get_budget_status` | Person's remaining budget + warning check (DM only) | No |
| `convert_currency` | Rate lookup / conversion | No |
| `create_reminder` | Schedule a reminder ("pay Airbnb by Friday") | No |

## 6. Agent behavior rules (decided)
- **Privacy:** individual budgets never appear in the group; budget info is DM-only. Group may see the group **average** only.
- **Budget = split share**, not what the person paid.
- **After every expense:** call `get_budget_status` for each person in the split; DM any warnings.
- **Default split:** if unclear who an expense is for, **ask** — never guess.
- **Rounding:** leftover cent goes to a random person in the split.
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
- ✅ Agent: system prompt v1, 20 backend tools + `send_message`, Qwen tool-calling loop, fake-chat CLI (`agent/`)
- ✅ Tests: every example replayed offline against the fake backend, the database and the API; live Qwen tests ready to run
- ✅ Django backend + tool API, GroupMe bot, Google sign-in, Next.js trip page (all tested offline)
- ⏳ Live Qwen runs and prompt tuning: waiting on Alibaba account verification
- ⏳ Not deployed yet; Supabase not connected
- The Oct 16 drafts (`schema.sql`, `examples.json`, etc.) were never in this repo and are superseded by the code above

## 8. Open questions (ask Romir — don't decide)
- [ ] **Budget warning logic** — more complex than "< 10% of total" (placeholder in use); Romir to explain. Blocks Examples 3 and 8.
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
5. Finish Examples 3 and 8 once the budget-warning logic is defined.
