# Trip Agent — examples.md

Worked examples showing Claude how to reason through each edge case.
Format: chat message → state snapshot → reasoning → tool calls → replies (group + DMs).
Multi-turn where confirmations are needed.

---

## Example 1 — Someone can't make it

### State snapshot
- Trip: Miami Spring Break (PLANNING), base currency USD
- Members: Aarav (leader), Priya, Jake, Mia
- leader_approval: [member changes, trip changes]
- Expenses: Airbnb $1,200 paid by Aarav, split 4 ways ($300 each)
- Activities: Boat tour, est. $400 total (not per person), attendees: all 4

### Turn 1
**Priya (group):** @tripbot guys I can't make it anymore, so sorry 😭

**Reasoning**
1. Priya is talking about herself, so this is a possible dropout. Removing a member is a bigger decision.
2. "Can't make it" could mean one day or the whole trip. Don't remove her yet. Ask her to confirm she means the whole trip.
3. This group routes member changes through the leader, so Aarav must also approve.
4. Set expectations now: she'll still owe her share of the Airbnb even after she's removed.

**Tool calls:** none yet

**Reply (group):**
> Sorry Priya! Just to confirm, are you out for the whole trip? @Aarav as trip lead, you'll need to approve too. Heads up: anything already booked (like the Airbnb) still gets split with you.

### Turn 2
**Priya (group):** @tripbot yeah whole trip
**Aarav (group):** @tripbot approved

**Reasoning**
1. Both confirmations are in: Priya confirmed, and Aarav (the leader) approved. OK to remove her.
2. Remove Priya. Her past splits stay. She comes off future splits and activities.
3. The boat tour's cost is a group total, not per person, so the per-person estimate goes up for the remaining 3.
4. Get her outstanding balance so she knows exactly what she owes and who to pay.
5. The remaining members' budgets may be affected by the higher boat tour share. Check each one, and DM only if there's a warning.

**Tool calls**
```
remove_member(trip_id="miami", person_id="priya")
  → { removed: true, removed_from_activities: ["boat_tour"] }

get_balances(trip_id="miami")
  → { priya: { owes: [{ to: "aarav", amount_cents: 30000, handle: "@aarav-venmo" }] } }

get_budget_status(trip_id="miami", person_id="aarav")  → { warnings: [] }
get_budget_status(trip_id="miami", person_id="jake")   → { warnings: [] }
get_budget_status(trip_id="miami", person_id="mia")    → { warnings: ["ACTIVITIES under 10% remaining"] }
```

**Reply (group):**
> Priya's off the trip 💔 Boat tour is now ~$133/person (was $100).

**Reply (DM → Priya):**
> Sorry you can't come! You still owe Aarav $300 for the Airbnb. Venmo: @aarav-venmo

**Reply (DM → Mia):**
> Heads up: with the boat tour going up to ~$133, your activities budget is almost used up.

---

## Example 2a — Date change

### State snapshot
- Trip: Miami Spring Break (BOOKED), Mar 14–18, base currency USD
- Members: Aarav (leader), Jake, Mia
- leader_approval: [member changes, trip changes]
- Expenses: Airbnb $1,200 for Mar 14–18, paid by Aarav
- Activities: Boat tour (Mar 15), Beach day (Mar 17)

### Turn 1
**Jake (group):** @tripbot can we push the trip to Mar 16–20? I have a midterm on the 15th

**Reasoning**
1. This is a trip change. Anyone can propose one, but this group routes trip changes through the leader, so Aarav must approve.
2. Check what the new dates break. The boat tour (Mar 15) falls outside Mar 16–20. The beach day (Mar 17) is fine.
3. The Airbnb is booked for the old dates, so flag it. Don't change any expense.
4. Don't change anything yet. Lay out the impact so Aarav can decide.

**Tool calls:** none yet

**Reply (group):**
> Jake wants to move the trip to Mar 16–20. @Aarav, your call as trip lead. If we do, the boat tour (Mar 15) falls outside the new dates, and the Airbnb is booked for Mar 14–18.

### Turn 2
**Aarav (group):** @tripbot yeah approved, I'll sort the Airbnb

**Reasoning**
1. The leader approved, so update the dates.
2. Conflicting activities get decided by the group one at a time. The boat tour is the only conflict, so ask about it.
3. Aarav said he'll handle the Airbnb, so don't raise it again.

**Tool calls**
```
update_trip(trip_id="miami", changes={start_date: "Mar 16", end_date: "Mar 20"})
  → { updated: true }
```

**Reply (group):**
> Dates updated to Mar 16–20 ✅ The boat tour (Mar 15) is now outside the trip. Move it to another day or drop it?

---

## Example 2b — Personal budget change

### State snapshot
- Mia's budget: $900 total, $300 spent (her split share)
- Upcoming activities with Mia attending: Boat tour (~$133/person), Club night (~$80/person)

### Turn 1
**Mia (DM):** can you lower my budget to $500

**Reasoning**
1. Budget info is private, so everything stays in DMs.
2. Save the new total, then check her status: $500 − $300 spent = $200 left.
3. Check her planned activities against that: boat tour ($133) + club night ($80) = $213. That's over her $200 by $13.
4. Tell her which plans no longer fit. Don't remove her from anything. That's her call.

**Tool calls**
```
set_budget(trip_id="miami", person_id="mia", total=50000, limits={})
  → { saved: true }
get_budget_status(trip_id="miami", person_id="mia")
  → { remaining_cents: 20000, warnings: [] }
```

**Reply (DM → Mia):**
> Done, your budget is now $500. You've got $200 left, but the boat tour (~$133) and club night (~$80) together come to ~$213, which is $13 over. Want to skip one or bump the budget a bit?

> Location changes follow the same pattern as 2a: leader approval if routed, keep expenses, and flag bookings and activities tied to the old place.

## Example 3 — Running out of budget early
TBD — waiting on Romir's budget warning logic

## Example 4a — Exclude someone from a split

### State snapshot
- Members: Aarav (leader), Jake, Mia. Base currency USD.

### Turn 1
**Mia (group):** @tripbot dinner was $120, I paid, split with everyone except Jake

**Reasoning**
1. This is an expense with a clear payer, amount, and split: everyone except Jake means Aarav and Mia.
2. No exact amounts are given, so it's an equal split: $60 each. It divides evenly, so there's no leftover cent.
3. Exclusions stated in a message just get logged. No confirmation needed.
4. After logging, check the budgets of everyone in the split (Aarav and Mia). DM only if there's a warning.

**Tool calls**
```
log_expense(trip_id="miami", paid_by="mia", amount=12000, currency="USD",
            description="Dinner", category="FOOD",
            split_with=["aarav", "mia"], exclude=["jake"], source_message="...")
  → { expense_id: "e7", splits: { aarav: 6000, mia: 6000 } }
get_budget_status(trip_id="miami", person_id="aarav")  → { warnings: [] }
get_budget_status(trip_id="miami", person_id="mia")    → { warnings: [] }
```

**Reply (group):**
> Logged 🍽️ Dinner, $120, paid by Mia, split between Aarav and Mia ($60 each). Jake's not included.

---

## Example 4b — Exact amounts + opt-out conflict

### State snapshot
- Members: Aarav (leader), Jake, Mia
- Exclusions: Jake opted out of DRINKS

### Turn 1
**Aarav (group):** @tripbot bar tab $90, I paid. I had $40, Mia $30, Jake $20

**Reasoning**
1. These are exact amounts. Check that they sum to the total: 40 + 30 + 20 = 90 ✓
2. The category is DRINKS, and Jake opted out of DRINKS, but he's explicitly named. That's a conflict, so ask before logging.
3. Don't log anything yet.

**Tool calls:** none yet

**Reply (group):**
> Quick check: Jake's opted out of drinks. @Jake, should I still put $20 of the bar tab on you?

### Turn 2
**Jake (group):** @tripbot yeah I had a couple sodas, include me

**Reasoning**
1. The conflict is resolved. Jake says to include him.
2. Log it with the exact amounts.
3. Check budgets for everyone in the split.

**Tool calls**
```
log_expense(trip_id="miami", paid_by="aarav", amount=9000, currency="USD",
            description="Bar tab", category="DRINKS",
            exact_amounts={ aarav: 4000, mia: 3000, jake: 2000 }, source_message="...")
  → { expense_id: "e8" }
get_budget_status(...) × 3  → { warnings: [] }
```

**Reply (group):**
> Logged 🍹 Bar tab, $90, paid by Aarav. Aarav $40, Mia $30, Jake $20.

## Example 5 — Travel tips for a given budget

### State snapshot
- Trip: Miami, Mar 16–20. Members: Aarav (leader), Jake, Mia
- Private budgets (set via DM): Aarav $1,200, Jake $800, Mia $500. Average is ~$833.

### Turn 1
**Jake (group):** @tripbot give us some tips for Miami

**Reasoning**
1. Tips depend on the group budget, and none has been picked yet.
2. All three members have set private budgets, so no DMs are needed to collect them. If someone hadn't set one, DM them first and wait.
3. Average ≈ $833. Build 3 tiers from it (placeholder rule: 0.75× / 1× / 1.25× ≈ $625 / $833 / $1,040).
4. Get tips for all 3 tiers, covering lodging, food, activities, and money-saving.
5. In the group, show only the average and the tier prices, never individual budgets.
6. The leader picks the tier, so tag Aarav.

**Tool calls**
```
get_budget_status(...) × 3   → totals used only to compute the average
get_travel_tips(trip_id="miami", destination="Miami",
                budget_tiers=[62500, 83300, 104000])
  → { tiers: [ {lodging, food, activities, saving_tips}, ... ] }
```

**Reply (group):**
> Group average is ~$833/person. Three ways to do Miami:
> 💸 **Budget (~$625):** hostel in South Beach, food trucks and Cuban spots, free beach days + Wynwood Walls
> 🌴 **Mid (~$833):** shared Airbnb, mix of casual and one nice dinner, boat tour
> 🥂 **Splurge (~$1,040):** hotel on Collins, nicer dinners, jet skis + a club night
> Money tip: Citi Bike + the free Miami Beach trolley instead of Ubers.
> @Aarav, pick one as the group budget?

### Turn 2
**Aarav (group):** @tripbot mid

**Reasoning**
1. The leader picked Mid, so save it as the group budget.
2. Future suggestions and itineraries should target ~$833/person.
3. Mia's budget ($500) is below Mid. DM her privately and nudge Aarav by DM, naming her.

**Tool calls**
```
update_trip(trip_id="miami", changes={ group_budget: 83300 })
```

**Reply (group):**
> Locked in: Mid (~$833/person) 🌴 I'll plan around that.

**Reply (DM → Mia):**
> Heads up: the group picked the Mid tier (~$833/person), which is above your budget. I'll flag cheaper options for you as we plan. Want to look at which parts to skip?

**Reply (DM → Aarav):**
> FYI: Mia's budget is below the Mid tier. Worth keeping a few cheaper options in the plan.

## Example 6 — Currency conversion

### State snapshot
- Trip: Cancún, base currency USD. Members: Aarav (leader), Jake, Mia
- Rates below are illustrative. The FX provider is TBD.

### Turn 1
**Jake (group):** @tripbot paid $1,800 for the snorkel tour

**Reasoning**
1. "$" in Mexico could mean USD or pesos, so ask. Don't guess.
2. He didn't say who it's for, and the default split rule is to ask.
3. Ask both questions in one message.

**Tool calls:** none yet

**Reply (group):**
> Got it! Was that $1,800 USD or pesos? And split with everyone?

### Turn 2
**Jake (group):** @tripbot pesos, everyone

**Reasoning**
1. 1,800 MXN needs converting to the base currency (USD), with the rate saved.
2. Equal split 3 ways. The leftover cent goes to a random person.
3. The confirmation shows both amounts.
4. Check budgets for all 3 people in the split.

**Tool calls**
```
convert_currency(amount=180000, from="MXN", to="USD")
  → { converted: 10000, rate: 0.0556 }
log_expense(trip_id="cancun", paid_by="jake", amount=180000, currency="MXN",
            description="Snorkel tour", category="ACTIVITIES",
            split_with=["aarav", "jake", "mia"], source_message="...")
  → { expense_id: "e9", base_amount: 10000, splits: { aarav: 3334, jake: 3333, mia: 3333 } }
get_budget_status(...) × 3  → { warnings: [] }
```

**Reply (group):**
> Logged 🤿 Snorkel tour, MX$1,800 (≈ $100), paid by Jake. ≈ $33.33 each.

## Example 7 — Blacklisted (category opt-out)

### State snapshot
- Members: Aarav (leader), Jake, Mia. No exclusions yet.

### Turn 1
**Jake (DM):** I don't drink, leave me out of drinks

**Reasoning**
1. This is a category opt-out for DRINKS. It can be set from a DM.
2. Save it. Future DRINKS expenses exclude Jake automatically.

**Tool calls**
```
set_exclusion(trip_id="miami", person_id="jake", category="DRINKS")
  → { saved: true }
```

**Reply (DM → Jake):**
> Done. You won't be included in any drinks splits.

### Turn 2
**Mia (group):** @tripbot drinks at the rooftop were $60, I paid, split with everyone

**Reasoning**
1. The category is DRINKS, and "everyone" means Aarav, Jake, and Mia.
2. Jake opted out of DRINKS and isn't explicitly named, so there's no conflict. Exclude him automatically.
3. Equal split between Aarav and Mia: $30 each.
4. The confirmation names Jake and gives the reason.
5. Check budgets for Aarav and Mia.

**Tool calls**
```
log_expense(trip_id="miami", paid_by="mia", amount=6000, currency="USD",
            description="Rooftop drinks", category="DRINKS",
            split_with=["aarav", "mia"], exclude=["jake"], source_message="...")
  → { expense_id: "e10", splits: { aarav: 3000, mia: 3000 } }
get_budget_status(...) × 2  → { warnings: [] }
```

**Reply (group):**
> Logged 🍸 Rooftop drinks, $60, paid by Mia, split between Aarav and Mia ($30 each). Jake's not included (opted out of drinks).

## Example 8 — Overspend advice
TBD — waiting on Romir's budget warning logic

## Example 9 — Refunds

### State snapshot
- Members: Aarav (leader), Jake, Mia
- leader_approval: [member changes, trip changes] (refunds not routed to leader)
- Expense e5: Concert tickets $300, paid by Aarav, split $100 each
- Jake already paid Aarav back $100 (SETTLEMENT). Mia hasn't paid yet.

### Turn 1
**Aarav (group):** @tripbot concert got moved, got $150 back on the tickets

**Reasoning**
1. Aarav is the original payer of e5, so he can report the refund.
2. Refunds are a big change, so confirm first. Refunds aren't routed to the leader in this group, so Aarav's confirmation is enough.
3. Same ratio as the original splits: $150 / 3 = $50 each.
4. Show him what will happen before recording anything.

**Tool calls:** none yet

**Reply (group):**
> Logging a $150 refund on Concert tickets ($300)? That's $50 back per person. Confirm?

### Turn 2
**Aarav (group):** @tripbot yep

**Reasoning**
1. Confirmed, so record the refund.
2. Jake already paid his $100, so Aarav now owes Jake $50. Mia hasn't paid, so her debt drops from $100 to $50.
3. Update balances, post in the group, and DM Aarav who to pay back.

**Tool calls**
```
record_refund(expense_id="e5", amount=15000, currency="USD", note="Concert moved")
  → { refund_id: "r1", per_person: { aarav: 5000, jake: 5000, mia: 5000 } }
get_balances(trip_id="miami")
  → { aarav: { owes: [{ to: "jake", amount_cents: 5000 }] },
      mia:   { owes: [{ to: "aarav", amount_cents: 5000 }] } }
```

**Reply (group):**
> Refund logged 🎟️ $150 back on Concert tickets, $50 per person. Mia now owes Aarav $50 (was $100).

**Reply (DM → Aarav):**
> Jake already paid you his $100, so send him $50 back. Venmo: @jake-venmo
