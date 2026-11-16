# Trip Agent — specs.md

## Purpose
Agent in a group chat that keeps track of a group trip's plans and manages group money (expenses, splits, per-person budgets that everyone on the trip can see).

> **Nov 12, 2026:** the bot no longer suggests or looks up places. Itinerary drafts, destination suggestions, nearby search and travel-tip tiers were removed. Planning is now a calendar of what the group decides.

## Features
- Log expenses
- Split costs
- Keep the trip's calendar (plans, ideas list, where the group is staying)

## Data model
The data model and its rules are implemented in `trip_model/` (see `trip_model/README.md`); `TripEngine` (`agent/backend/core/engine.py`) runs the tools on it. The MVP is USD-only; the currency fields and decisions below are post-MVP.

Category enum: LODGING, TRANSPORT, FOOD, DRINKS, ACTIVITIES, OTHER, SETTLEMENT

- **Person**: id, name, chat_user_id, payment_handle, budget (for this trip; shared with the trip), trips
- **Budget**: owner_id, total_cents, limits {Category: cents}; remaining(category, expenses); warn when a category's remaining minus planned activity costs < 10% of that category's limit (category limits only; the total doesn't warn)
- **Expense**: id, paid_by, amount_cents, description, category, splits {person_id: cents} (net change per person: + is owed, − owes; sums to 0), created_at, source_message. A person's share = what they paid − their split
- **Activity**: id, name, location, start, end, slot (morning / lunch / afternoon / dinner / night, only when the group named one; start is then just the day), est_cost_cents, cost_is_per_person, attendees, important, booking_url, expense_id, from_idea
- **Poll**: id, question, options, votes {person_id: option}, closes_at, is_open
- **Reminder**: message, due_at, audience (list | "all"), sent, created_by ("agent" | "system")
- **Trip**: id, name, status (PLANNING / BOOKED / ACTIVE / DONE), destination?, start_date?, end_date?, target_break?, members, activities, expenses, polls, reminders

### Data decisions
- **Currency:** Expense stores original amount + currency AND converted amount in the trip's base currency; rate saved at log time.
- **Refunds:** separate Refund record referencing the original expense.
- **Dropouts:** past splits stay (they still owe); removed from future splits and activities only.
- **Rounding:** leftover cents on uneven equal splits go to people in id order; percentage and proportional splits give them to the largest remainders (ties in id order). The same expense always splits the same way.
- **Budget:** counts a person's split share of each expense, not what they paid.
- **Payer outside the split:** the payer doesn't have to be in the split (e.g. a non-drinker puts the bar tab on their card). Their share is $0 and they're owed the full amount by the people in the split.
- **Settlements:** a payback is recorded with `record_payback` as a SETTLEMENT expense (paid_by = sender, the receiver's balance goes down). Balances are netted across the group into one number per person, and the agent suggests payments: exact opposites pay each other first, then the biggest debtor pays the biggest creditor (at most n − 1 payments). Someone may be told to pay a person other than the one who paid for their stuff. The plan is only a suggestion. SETTLEMENT doesn't count toward budgets.
- **Blacklist:** (1) person exclusions — decided per expense (e.g. someone didn't go to a specific lunch); (2) per-person category opt-outs — a person opts out of a whole category (e.g. not drinking → DRINKS).
- **Refund distribution:** refunds go back in the same ratio as the original shares.
- **Poll results:** when a poll closes, the agent posts the winner and asks before updating the trip.
- **Group budget:** the leader sets a per-person budget for the group as a number. If someone's own budget is below it, the agent says so in the group, kindly, and makes sure the leader sees it. Members without a budget are asked for one. (Travel-tip tiers were removed Nov 12, 2026.)
- **Plans:** a plan with just a day has no time. It gets a slot only when someone names one, and any number of plans can share a slot. A clock time is saved as given. Two plans at exactly the same clock time on a day need the person's "yes" first. Moving a plan to another day keeps its time or slot.
- **Trip state:** each turn the agent gets a short `Trip.summary()` (members with their budget totals, leader, leader_approval, exclusions, recent expenses, activities, open polls). For anything else it calls `get_trip`.
- **Currency:** if a currency symbol is ambiguous (e.g. "$" abroad), the agent asks. Confirmations show both amounts (e.g. "€90 (≈ $97)"). People settle up in whatever currency they choose, and the agent converts.

## Agent rules
- **Shared budgets (decided Oct 28, 2026):** each person's budget for the trip, what's left and their warnings are visible to everyone on the trip. The agent only posts in the group and tags a person with @Name when a message is for them. Only the person sets their own budget.
- **Confirmation:** confirm before big changes (removing a member, refunds, trip changes); simple expense logs happen immediately.
- **Group leader:** set manually by the group (can change later). During onboarding, the group decides which decision types need leader approval. Options: trip changes, member changes, refunds/deletes. There is no default. Decisions that need the leader require leader approval; smaller ones need the person's confirmation plus the group's.
- **Dropouts:** count as a bigger decision. Anyone can say someone's out, but the person must confirm. If the group routed member changes to the leader, the leader also approves. The person is removed immediately but still owes their past splits until they're paid.

- **Expense edits/deletes:** any member can request; the payer must confirm.
- **Default split:** if the sender doesn't say who an expense is for, the agent asks. It never guesses.
- **Split types:** equal among chosen people, exact amounts per person (which must sum to the total), or percentages of that one expense (which must sum to 100).
- **Exclusions in a message:** e.g. "everyone except Jake" — just log it.
- **Category opt-outs:** set in the group. When an expense auto-excludes someone, the confirmation names them and gives the reason.
- **Refunds:** only the original payer reports a refund. Balances update and the agent posts the new suggested payments. If people already paid the payer back, the agent tells each of them in the group what happens to their money (who will pay them).
- **Paybacks:** recorded with `record_payback` only once the payment really happened (the sender says they paid, or the receiver confirms).
- **Opt-out conflict:** if someone opted out of a category but is explicitly named in a split for that category, the agent asks before logging.
- **Budget checks:** after every expense, the agent calls `get_budget_status` for each person in the split and posts any warnings in the group, tagging the person.
- **Places:** the agent never suggests, looks up or recommends places, and never makes up prices or opening hours. Asked for that ("pizza near us?", "plan our days"), it says so in one short line, and offers something else only when it clearly fits.

## Platform & listening
- **Platform:** GroupMe for now.
- **Listening:** the agent reads every group message and extracts trip data automatically. It replies when @mentioned, and speaks up unprompted only for important warnings: budget warnings, date/booking conflicts, unpaid debts, and upcoming deadlines.
- **Auto-logging extracted expenses:** the group picks a mode during onboarding (no default).
- **No DMs:** GroupMe bots can't send DMs, so everything goes to the group.

## Tools
Amounts in cents. "Confirm" = agent must get the stated confirmation before calling.

### Expenses
| Tool | Does | Inputs | Confirm |
|---|---|---|---|
| `log_expense` | Logs a payment and its splits; saves original + base-currency amounts and the rate; leftover cents in id order; applies blacklist exclusions/opt-outs. Returns shares (what each person owes for it) and splits (net changes) | trip_id, paid_by, amount, currency, description, category, split_with[] OR exact_amounts{person_id: amount} OR percentages{person_id: percent}, exclude[], source_message | No |
| `edit_expense` | Changes amount, category, description, or split_with | expense_id, requested_by, changes{} | Payer |
| `delete_expense` | Removes a wrongly logged expense | expense_id, requested_by | Payer |
| `record_refund` | Creates a Refund record against an expense | expense_id, amount, currency, note | Yes |
| `record_payback` | Records a real off-app payment (Venmo, Zelle, cash) as a SETTLEMENT; lowers what the sender owes | trip_id, from_person, to_person, amount, currency | The payment happened |

### Trip & members
| Tool | Does | Inputs | Confirm |
|---|---|---|---|
| `add_member` | Adds someone to the trip | trip_id, chat_user_id, name, payment_handle? | No |
| `remove_member` | Drops someone; past splits stay, removed from future splits + activities | trip_id, person_id | Yes |
| `update_trip` | Changes destination, dates, base currency, status, target_break, group_budget, leader_id, leader_approval. A group_budget change returns the members whose budget is below it | trip_id, changes{} | Yes |
| `set_budget` | Sets a person's total + category limits for this trip | trip_id, person_id, total, limits{} | No |
| `set_exclusion` | Blacklist: opt a person out of a category (per-expense exclusions go through `exclude[]` on `log_expense`) | trip_id, person_id, category | No |

### Planning
| Tool | Does | Inputs | Confirm |
|---|---|---|---|
| `add_activity` | Adds/edits/moves one plan: just a day, a named slot, or a clock time. Saves nothing if another plan is at exactly that clock time, until called again with confirm_same_time | trip_id, activity fields, day?, slot?, idea_id?, confirm_same_time? | Only for the same clock time |
| `remove_activity` | Removes a plan; one from the ideas list goes back on it | trip_id, activity_id | If paid for or important |
| `save_idea` | Adds or removes an idea (no day yet, up to 20) | trip_id, name, est_cost_cents?, remove? | No |
| `create_poll` | Starts a group vote | trip_id, question, options[], closes_at | No |
| `vote_poll` | Records a vote from a chat reply | poll_id, person_id, option | No |
| `close_poll` | Closes a poll and returns the winner (trip update needs group confirmation via `update_trip`) | poll_id | No |
| `create_reminder` | Schedules a reminder | trip_id, message, due_at, audience | No |

### Money info
| Tool | Does | Inputs | Visibility |
|---|---|---|---|
| `get_balances` | Net balance per person + suggested payments (netted across the group, with handles) | trip_id | Group |
| `get_budget_status` | A person's remaining budget + warnings | trip_id, person_id | Group |
| `convert_currency` | Converts an amount | amount, from, to | Group |
| `get_trip` | Full trip state: members, leader, leader_approval, exclusions, expenses, refunds, activities, polls, reminders, budgets | trip_id | Group |

### Chat (handled by the bot, not the backend)
| Tool | Does | Inputs |
|---|---|---|
| `send_message` | The only way the agent talks: posts in the group chat | text |

### Model changes implied by the decisions above
- Trip: + base_currency, leader_id, leader_approval (set of decision types chosen at onboarding), group_budget (per person, set by the leader), lodging (text, as the group wrote it)
- Expense: + original_amount, original_currency, fx_rate
- Refund: new (expense_id, amount, currency, note, created_at)
- Exclusion: new (person_id, category) — category opt-outs

## Open questions
- [x] Budget warning logic → under 10% of a category's limit left, counting planned activities; category limits only
- [ ] FX rate provider — ask mentor (harness uses a fixed rate table for now)
- [x] How tier prices are derived from the average → tiers removed Nov 12, 2026; the leader sets the group budget directly
- [x] How the agent reads saved trip state on later messages → both: injected summary every turn + `get_trip` tool
- [x] Can GroupMe bots DM? → no, and budgets are shared now, so the bot only posts in the group

## Edge cases (→ examples.md)
- Someone can't make it → recalc budgets, confirm
- Change of location / budget / date
- Running out of budget early → warning
- Split among / exclude specific people
- Currency conversion
- Blacklisted items
- Overspend advice
- Refunds
