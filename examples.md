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
  → { suggested_payments: [{ from: "priya", to: "aarav", amount_cents: 30000, handle: "@aarav-venmo" }, ...] }

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

### State snapshot
- Trip in progress: Miami, Mar 14–18. It's the evening of Mar 15.
- Members: Aarav (leader), Jake, Mia
- Mia's private budget: $900 total, FOOD limit $150. Aarav: $1,500 total, no category limits. Jake hasn't set one.
- Expenses so far: Brunch $120 (paid by Aarav), Dinner $210 (paid by Jake), both split 3 ways. Mia's food spending: $40 + $70 = $110.

### Turn 1
**Jake (group):** @tripbot tacos were $90, I got it, split with everyone

**Reasoning**
1. Clear payer, amount and split: log it right away. $90 / 3 = $30 each.
2. After every expense, check the budget of everyone in the split.
3. Mia's food spending is now $140 of her $150 limit: under 10% left, and the trip has three more days. That's a warning, so DM her.
4. Her budget is private: the group confirmation doesn't mention it.

**Tool calls**
```
log_expense(trip_id="miami", paid_by="jake", amount=9000, currency="USD",
            description="Tacos", category="FOOD",
            split_with=["aarav", "jake", "mia"], source_message="...")
  → { expense_id: "e3", shares: { aarav: 3000, jake: 3000, mia: 3000 } }
get_budget_status(trip_id="miami", person_id="aarav")  → { warnings: [] }
get_budget_status(trip_id="miami", person_id="jake")   → { budget_set: false, warnings: [] }
get_budget_status(trip_id="miami", person_id="mia")
  → { by_category: { FOOD: { limit_cents: 15000, spent_cents: 14000 } },
      warnings: ["FOOD under 10% remaining"] }
```

**Reply (group):**
> Logged 🌮 Tacos, $90, paid by Jake, split 3 ways ($30 each).

**Reply (DM → Mia):**
> Heads up: you've got $10 left of your $150 food budget, and the trip runs through Mar 18. Want some cheaper food ideas, or should I raise your food limit?

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
  → { expense_id: "e7", shares: { aarav: 6000, mia: 6000 } }
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
- leader_approval: [member changes, trip changes]
- Private budgets (set via DM): Aarav $1,200, Jake $800, Mia $500. Average is ~$833.
- Tier presets: 0.5× / 0.75× / 1× / 1.25× / 1.5× / 2× of the group average, or any custom multiplier.

### Turn 1
**Jake (group):** @tripbot give us some tips for Miami

**Reasoning**
1. Tips depend on the group budget, and none has been picked yet.
2. All three members have set private budgets, so no DMs are needed to collect them. If someone hadn't set one, DM them first and wait.
3. List the 6 preset tiers first, with prices only. No tips yet. The backend works out the prices from the group average, so individual budgets never reach the chat.
4. In the group, show only the average and the tier prices, never individual budgets.
5. Anyone can pick a preset or ask for a custom multiplier. Only the leader locks one in.

**Tool calls**
```
get_travel_tips(trip_id="miami", destination="Miami",
                multipliers=[0.5, 0.75, 1, 1.25, 1.5, 2], prices_only=true)
  → { average_cents: 83333, missing_budgets: [],
      tiers: [ {multiplier: 0.5, budget_cents: 41700}, {multiplier: 0.75, budget_cents: 62500},
               {multiplier: 1, budget_cents: 83300}, {multiplier: 1.25, budget_cents: 104200},
               {multiplier: 1.5, budget_cents: 125000}, {multiplier: 2, budget_cents: 166700} ] }
```

**Reply (group):**
> Group average is ~$833/person. Pick a level and I'll pull tips for it:
> 0.5× ~$417 · 0.75× ~$625 · 1× ~$833 · 1.25× ~$1,042 · 1.5× ~$1,250 · 2× ~$1,667
> Or name your own multiplier (like 1.1×). @Aarav locks in the final pick.

### Turn 2
**Jake (group):** @tripbot show us 1.1x

**Reasoning**
1. Jake proposed a custom multiplier. Anyone can propose, so fetch tips for that one tier.
2. 1.1 × ~$833 ≈ $917. Tips cover lodging, food, activities, and money-saving.
3. Proposing isn't locking in. Ask Aarav (the leader) to confirm before saving it as the group budget.

**Tool calls**
```
get_travel_tips(trip_id="miami", destination="Miami", multipliers=[1.1])
  → { average_cents: 83333,
      tiers: [ {multiplier: 1.1, budget_cents: 91700, lodging, food, activities, saving_tips} ] }
```

**Reply (group):**
> Miami at ~$917/person (1.1×) 🌴
> 🏠 Shared Airbnb near South Beach
> 🍽️ Casual spots + one nice dinner
> 🚤 Boat tour and a beach day
> 💡 Citi Bike + the free Miami Beach trolley instead of Ubers
> @Aarav, lock this in as the group budget?

### Turn 3
**Aarav (group):** @tripbot yeah lock it in

**Reasoning**
1. The leader confirmed, so save ~$917 as the group budget.
2. Future suggestions and itineraries should target ~$917/person.
3. The update says Mia's private budget is below the new group budget. DM her privately and nudge Aarav by DM, naming her but not her number.

**Tool calls**
```
update_trip(trip_id="miami", changes={ group_budget: 91700 })
  → { updated: true, members_below_group_budget: ["mia"] }
```

**Reply (group):**
> Locked in: ~$917/person (1.1×) 🌴 I'll plan around that.

**Reply (DM → Mia):**
> Heads up: the group budget is ~$917/person, which is above your budget. I'll flag cheaper options for you as we plan. Want to look at which parts to skip?

**Reply (DM → Aarav):**
> FYI: Mia's budget is below the group budget. Worth keeping a few cheaper options in the plan.

## Example 6 — Currency conversion

> **Post-MVP.** The MVP is USD-only. This example stays so the currency code keeps being tested.

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
2. Equal split 3 ways. The leftover cent goes to the first person in id order (Aarav).
3. The confirmation shows both amounts.
4. Check budgets for all 3 people in the split.

**Tool calls**
```
convert_currency(amount=180000, from="MXN", to="USD")
  → { converted: 10000, rate: 0.0556 }
log_expense(trip_id="cancun", paid_by="jake", amount=180000, currency="MXN",
            description="Snorkel tour", category="ACTIVITIES",
            split_with=["aarav", "jake", "mia"], source_message="...")
  → { expense_id: "e9", base_amount: 10000, shares: { aarav: 3334, jake: 3333, mia: 3333 } }
get_budget_status(...) × 3  → { warnings: [] }
```

**Reply (group):**
> Logged 🤿 Snorkel tour, MX$1,800 (≈ $100), paid by Jake. ≈ $33.33 each.

## Example 7a — Blacklisted (category opt-out)

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
  → { expense_id: "e10", shares: { aarav: 3000, mia: 3000 } }
get_budget_status(...) × 2  → { warnings: [] }
```

**Reply (group):**
> Logged 🍸 Rooftop drinks, $60, paid by Mia, split between Aarav and Mia ($30 each). Jake's not included (opted out of drinks).

## Example 7b — Payer isn't in the split

### State snapshot
- Trip: Miami Spring Break, base currency USD
- Members: Aarav (leader), Priya, Jake, Mia, Sam, Leo, Nina, Zoe (8 people)
- Exclusions: Jake opted out of DRINKS (he doesn't drink)

### Turn 1
**Jake (group):** @tripbot bar tab was $350, put it on my card, split with everyone

**Reasoning**
1. The category is DRINKS. Jake is the payer, but he opted out of DRINKS and isn't explicitly named in the split, so he's auto-excluded.
2. Paying for something isn't the same as taking part in it. Jake stays the payer even though he's not in the split. That's not a conflict, so no need to ask.
3. "Everyone" minus Jake is 7 people. Equal split: $350 / 7 = $50 each. It divides evenly, so there's no leftover cent.
4. Jake's share is $0, so he's owed the full $350: each of the 7 owes Jake $50.
5. Check budgets for the 7 people in the split. Jake fronted the money but spent nothing, so his budget doesn't change.

**Tool calls**
```
log_expense(trip_id="miami", paid_by="jake", amount=35000, currency="USD",
            description="Bar tab", category="DRINKS",
            split_with=["aarav", "priya", "mia", "sam", "leo", "nina", "zoe"],
            exclude=["jake"], source_message="...")
  → { expense_id: "e11", shares: { aarav: 5000, priya: 5000, mia: 5000, sam: 5000,
                                   leo: 5000, nina: 5000, zoe: 5000 } }
get_budget_status(...) × 7  → { warnings: [] }
```

**Reply (group):**
> Logged 🍻 Bar tab, $350, paid by Jake, split between the 7 drinkers ($50 each). Jake's not included (opted out of drinks), so everyone owes Jake $50. Venmo: @jake-venmo

## Example 8 — Overspend advice

### State snapshot
- Trip in progress: Miami, Mar 14–18. It's midday on Mar 16.
- Members: Aarav (leader), Jake, Mia
- Mia's private budget: $900 total, FOOD limit $150
- Food so far, all split 3 ways: Brunch $120, Dinner $210, Tacos $90, Lunch $60. Mia's share: $160, so she's $10 over her food limit.

### Turn 1
**Mia (DM):** I'm over on food aren't I? what should I do

**Reasoning**
1. Budget talk, and she asked in a DM: answer only in her DM.
2. Check her real numbers with `get_budget_status` instead of guessing.
3. Advice should come from the travel-tips tool, not my own knowledge. The cheapest tier (0.5×) has the money-saving food ideas.
4. She's over on one category but has plenty left overall, so offer to raise the food limit. Don't change anything until she says so.

**Tool calls**
```
get_budget_status(trip_id="miami", person_id="mia")
  → { total_cents: 90000, remaining_cents: 74000,
      by_category: { FOOD: { limit_cents: 15000, spent_cents: 16000 } },
      warnings: ["FOOD over limit by $10 including planned activities"] }
get_travel_tips(trip_id="miami", destination="Miami", multipliers=[0.5])
  → { tiers: [{ multiplier: 0.5, food: "Street food, food trucks and grocery-store breakfasts", ... }] }
```

**Reply (DM → Mia):**
> Yeah, you're $10 over your $150 food limit, but you've still got $740 left overall. Cheaper ideas for the next two days: street food, food trucks and grocery-store breakfasts. Want me to raise your food limit (say to $200) so it matches how you're actually spending?

### Turn 2
**Mia (DM):** yeah make it $200

**Reasoning**
1. Setting your own budget needs no confirmation. Keep her $900 total; only the food limit changes.
2. Check the new status and tell her what's left.

**Tool calls**
```
set_budget(trip_id="miami", person_id="mia", total=90000, limits={ FOOD: 20000 })
get_budget_status(trip_id="miami", person_id="mia")
  → { by_category: { FOOD: { limit_cents: 20000, spent_cents: 16000 } }, warnings: [] }
```

**Reply (DM → Mia):**
> Done, your food limit is now $200 (total still $900). You've got $40 left for food.

## Example 9 — Refunds

### State snapshot
- Members: Aarav (leader), Jake, Mia
- leader_approval: [member changes, trip changes] (refunds not routed to leader)
- Expense e5: Concert tickets $300, paid by Aarav, split $100 each
- Jake already paid Aarav back $100 (recorded with `record_payback`). Mia hasn't paid yet.

### Turn 1
**Aarav (group):** @tripbot concert got moved, got $150 back on the tickets

**Reasoning**
1. Aarav is the original payer of e5, so he can report the refund.
2. Refunds are a big change, so confirm first. Refunds aren't routed to the leader in this group, so Aarav's confirmation is enough.
3. Same ratio as the original shares: $150 / 3 = $50 each.
4. Show him what will happen before recording anything.

**Tool calls:** none yet

**Reply (group):**
> Logging a $150 refund on Concert tickets ($300)? That's $50 back per person. Confirm?

### Turn 2
**Aarav (group):** @tripbot yep

**Reasoning**
1. Confirmed, so record the refund.
2. Everyone's share drops to $50. Jake already paid $100, so he's owed $50 back. Mia hasn't paid, so she owes $50. Aarav comes out even.
3. Balances are netted across the group, so the suggested payment is Mia → Jake $50 directly. Aarav doesn't have to pass money along.
4. Post the new settle-up in the group, and DM Jake so he knows where his $50 is coming from.

**Tool calls**
```
record_refund(expense_id="e5", amount=15000, currency="USD", note="Concert moved")
  → { refund_id: "r1", per_person: { aarav: 5000, jake: 5000, mia: 5000 } }
get_balances(trip_id="miami")
  → { net_balances: { jake: 5000, mia: -5000 },
      suggested_payments: [{ from: "mia", to: "jake", amount_cents: 5000, handle: "@jake-venmo" }] }
```

**Reply (group):**
> Refund logged 🎟️ $150 back on Concert tickets, $50 per person. To settle up: Mia sends Jake $50 (Venmo: @jake-venmo) and Aarav's all square.

**Reply (DM → Jake):**
> You'd already paid Aarav your $100, so after the refund you're owed $50. Mia's sending it to you directly, so Aarav doesn't need to pay you back.
