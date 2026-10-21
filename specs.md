# Trip Agent — specs.md

## Purpose
Agent in a group chat that plans a group trip, builds the itinerary, and manages group money (expenses, splits, private per-person budgets).

## Features
- Log expenses
- Split costs
- Travel tips
- Generate itinerary

## Data model
Category enum: LODGING, TRANSPORT, FOOD, DRINKS, ACTIVITIES, OTHER, SETTLEMENT

- **Person**: id, name, chat_user_id, payment_handle, budget (private), trips
- **Budget**: owner_id, total_cents, limits {Category: cents}; remaining(category, expenses); warn when remaining < 10% of total
- **Expense**: id, paid_by, amount_cents, description, category, splits {person_id: cents} (sums to amount_cents), created_at, source_message
- **Activity**: id, name, location, start, end, est_cost_cents, cost_is_per_person, attendees, important, booking_url, expense_id
- **Poll**: id, question, options, votes {person_id: option}, closes_at, is_open
- **Reminder**: message, due_at, audience (list | "all"), sent, created_by ("claude" | "system")
- **Trip**: id, name, status (PLANNING / BOOKED / ACTIVE / DONE), destination?, start_date?, end_date?, target_break?, members, activities, expenses, polls, reminders

### Data decisions
- **Currency:** Expense stores original amount + currency AND converted amount in the trip's base currency; rate saved at log time.
- **Refunds:** separate Refund record referencing the original expense.
- **Dropouts:** past splits stay (they still owe); removed from future splits and activities only.
- **Rounding:** leftover cents on uneven splits assigned randomly per expense.
- **Budget:** counts a person's split share of each expense, not what they paid.
- **Blacklist:** (1) person exclusions — decided per expense (e.g. someone didn't go to a specific lunch); (2) per-person category opt-outs — a person opts out of a whole category (e.g. not drinking → DRINKS).
- **Refund distribution:** refunds go back in the same ratio as the original splits.
- **Poll results:** when a poll closes, the agent posts the winner and asks before updating the trip.
- **Travel tips & budget:** the agent collects each member's budget by DM and works out the group average. It proposes 3 tiers (budget / mid / splurge), and the leader picks one as the group budget. In the group, it reveals only the average, never anyone's individual budget. Tips cover lodging, food, activities, and money-saving tips. If someone's private budget is below the chosen tier, the agent DMs them and also nudges the leader, naming the person.
- **Currency:** if a currency symbol is ambiguous (e.g. "$" abroad), the agent asks. Confirmations show both amounts (e.g. "€90 (≈ $97)"). People settle up in whatever currency they choose, and the agent converts.

## Agent rules
- **Privacy:** anything about a person's budget (remaining, warnings, overspend advice) goes by DM only, never the group chat.
- **Confirmation:** confirm before big changes (removing a member, refunds, trip changes); simple expense logs happen immediately.
- **Group leader:** set manually by the group (can change later). During onboarding, the group decides which decision types need leader approval. Options: trip changes, member changes, itinerary saves, refunds/deletes. There is no default. Decisions that need the leader require leader approval; smaller ones need the person's confirmation plus the group's.
- **Dropouts:** count as a bigger decision. Anyone can say someone's out, but the person must confirm. If the group routed member changes to the leader, the leader also approves. The person is removed immediately but still owes their past splits until they're paid.

- **Expense edits/deletes:** any member can request; the payer must confirm.
- **Default split:** if the sender doesn't say who an expense is for, the agent asks. It never guesses.
- **Split types:** equal among chosen people, or exact amounts per person (which must sum to the total).
- **Exclusions in a message:** e.g. "everyone except Jake" — just log it.
- **Category opt-outs:** can be set by DM or in the group. When an expense auto-excludes someone, the confirmation names them and gives the reason.
- **Refunds:** only the original payer reports a refund. If people already paid the payer back, balances update and the agent DMs the payer who to pay back and how much.
- **Opt-out conflict:** if someone opted out of a category but is explicitly named in a split for that category, the agent asks before logging.
- **Budget checks:** after every expense, the agent calls `get_budget_status` for each person in the split and DMs any warnings.
- **Travel info:** tips and itinerary places come from external APIs (Google Places / SerpAPI), not Claude's own knowledge.

## Platform & listening
- **Platform:** GroupMe for now.
- **Listening:** the agent reads every group message and extracts trip data automatically. It replies when @mentioned, and speaks up unprompted only for important warnings: budget warnings, date/booking conflicts, unpaid debts, and upcoming deadlines.
- **Auto-logging extracted expenses:** the group picks a mode during onboarding (no default).
- **Risk:** GroupMe bots may not be able to send DMs, which would break the DM-only budget rule. Verify this.

## Tools
Amounts in cents. "Confirm" = agent must get the stated confirmation before calling.

### Expenses
| Tool | Does | Inputs | Confirm |
|---|---|---|---|
| `log_expense` | Logs a payment and its splits; saves original + base-currency amounts and the rate; random leftover cent; applies blacklist exclusions/opt-outs | trip_id, paid_by, amount, currency, description, category, split_with[] OR exact_amounts{person_id: amount}, exclude[], source_message | No |
| `edit_expense` | Changes amount, category, description, or split_with | expense_id, requested_by, changes{} | Payer |
| `delete_expense` | Removes a wrongly logged expense | expense_id, requested_by | Payer |
| `record_refund` | Creates a Refund record against an expense | expense_id, amount, currency, note | Yes |

### Trip & members
| Tool | Does | Inputs | Confirm |
|---|---|---|---|
| `add_member` | Adds someone to the trip | trip_id, chat_user_id, name, payment_handle? | No |
| `remove_member` | Drops someone; past splits stay, removed from future splits + activities | trip_id, person_id | Yes |
| `update_trip` | Changes destination, dates, base currency, status, target_break, leader_id, leader_approval | trip_id, changes{} | Yes |
| `set_budget` | Sets a person's private total + category limits (DM only) | trip_id, person_id, total, limits{} | No |
| `set_exclusion` | Blacklist: opt a person out of a category (per-expense exclusions go through `exclude[]` on `log_expense`) | trip_id, person_id, category | No |

### Planning
| Tool | Does | Inputs | Confirm |
|---|---|---|---|
| `generate_itinerary` | Builds a day-by-day draft via Places/SerpAPI; posts it; saves as Activities only after group confirms | trip_id, constraints | Yes (before saving) |
| `add_activity` | Adds/edits one activity | trip_id, activity fields | No |
| `get_travel_tips` | Tips via external APIs across multiple budget tiers built from the group budget | trip_id, destination, budget_tiers[], interests? | No |
| `create_poll` | Starts a group vote | trip_id, question, options[], closes_at | No |
| `vote_poll` | Records a vote from a chat reply | poll_id, person_id, option | No |
| `close_poll` | Closes a poll and returns the winner (trip update needs group confirmation via `update_trip`) | poll_id | No |
| `create_reminder` | Schedules a reminder | trip_id, message, due_at, audience | No |

### Money info
| Tool | Does | Inputs | Visibility |
|---|---|---|---|
| `get_balances` | Who owes whom | trip_id | Group |
| `get_budget_status` | A person's remaining budget + warnings | trip_id, person_id | DM only |
| `convert_currency` | Converts an amount | amount, from, to | Group |

### Model changes implied by the decisions above
- Trip: + base_currency, leader_id, leader_approval (set of decision types chosen at onboarding), group_budget (tier the leader picked)
- Expense: + original_amount, original_currency, fx_rate
- Refund: new (expense_id, amount, currency, note, created_at)
- Exclusion: new (person_id, category) — category opt-outs

## Open questions
- [ ] Budget warning logic — Romir to explain (more complex than < 10% of total)
- [ ] FX rate provider — ask mentor
- [ ] How tier prices are derived from the average (example 5 uses placeholder 0.75× / 1× / 1.25×)
- [ ] How the agent reads saved trip state on later messages (injected summary vs get_trip tool)
- [ ] Can GroupMe bots DM? If not, how do private budget messages get delivered?

## Edge cases (→ examples.md)
- Someone can't make it → recalc budgets, confirm
- Change of location / budget / date
- Running out of budget early → warning
- Split among / exclude specific people
- Travel tips for a given budget
- Currency conversion
- Blacklisted items
- Overspend advice
- Refunds
