# Agent eval report

- **Model:** `qwen3.8-flash` (thinking on)
- **Date:** 2026-10-23
- **Runs:** 81 (27 scenarios)
- **Overall:** 81/81 runs passed (100%); 27/27 scenarios passed every run

Each run plays a scenario's chat messages to the agent against a fresh fake trip, then checks what it did (tool calls, who it messaged, what changed) and that no budget leaked into the group.

| Scenario | Source | What it checks | Passed | Avg sec / turn | Avg tokens / turn |
|---|---|---|---|---|---|
| `edge_ambiguous_split` | edge case | An expense without who it's for gets a question, not a guess | ✅ 3/3 | 9.4 | 16,505 |
| `edge_delete_needs_payer` | edge case | Deleting someone else's expense waits for the payer | ✅ 3/3 | 8.6 | 21,809 |
| `edge_dropout_no_leader_routing` | edge case | A clear dropout needs only the person when member changes aren't routed to the leader | ✅ 3/3 | 20.6 | 42,827 |
| `edge_edit_needs_payer` | edge case | Editing someone else's expense waits for the payer | ✅ 3/3 | 8.5 | 23,333 |
| `edge_euro_amount` | edge case | A euro amount is unambiguous, so it's logged without asking | ✅ 3/3 | 22.1 | 34,089 |
| `edge_exact_amounts_mismatch` | edge case | Exact amounts that don't add up get a question | ✅ 3/3 | 11.9 | 28,095 |
| `edge_itinerary_needs_leader` | edge case | Saving an itinerary waits for the leader when itinerary saves are routed to them | ✅ 3/3 | 8.2 | 26,011 |
| `edge_onboarding` | edge case | A brand-new trip gets set up through chat | ✅ 3/3 | 6.8 | 23,322 |
| `edge_opt_back_in` | edge case | Opting back into a category | ✅ 3/3 | 7.3 | 27,456 |
| `edge_own_budget_in_group` | edge case | Someone asks about their own budget in the group chat | ✅ 3/3 | 11.2 | 28,235 |
| `edge_poll_flow` | edge case | Poll from start to applying the result | ✅ 3/3 | 8.7 | 28,876 |
| `edge_privacy_dm_ask` | edge case | Someone DMs the bot asking for another person's budget | ✅ 3/3 | 5.1 | 16,490 |
| `edge_privacy_group_ask` | edge case | Someone asks the group bot for another person's budget | ✅ 3/3 | 8.3 | 16,633 |
| `edge_quiet_unmentioned` | edge case | Small talk without a mention gets no reply | ✅ 3/3 | 4.9 | 16,313 |
| `edge_reminder` | edge case | A reminder with a weekday becomes a dated reminder | ✅ 3/3 | 15.5 | 34,082 |
| `ex1_dropout` | Example 1 | Someone can't make it | ✅ 3/3 | 13.2 | 31,231 |
| `ex2a_date_change` | Example 2a | Date change | ✅ 3/3 | 12.2 | 26,125 |
| `ex2b_budget_change` | Example 2b | Personal budget change | ✅ 3/3 | 13.5 | 35,085 |
| `ex3_running_out_early` | Example 3 | Running out of budget early | ✅ 3/3 | 10.6 | 31,616 |
| `ex4a_exclude_person` | Example 4a | Exclude someone from a split | ✅ 3/3 | 10.6 | 33,804 |
| `ex4b_exact_amounts_conflict` | Example 4b | Exact amounts + opt-out conflict | ✅ 3/3 | 41.1 | 23,312 |
| `ex5_travel_tips` | Example 5 | Travel tips for a given budget | ✅ 3/3 | 14.7 | 39,424 |
| `ex6_currency` | Example 6 | Currency conversion | ✅ 3/3 | 9.4 | 24,661 |
| `ex7a_category_opt_out` | Example 7a | Blacklisted (category opt-out) | ✅ 3/3 | 8.8 | 27,263 |
| `ex7b_payer_outside_split` | Example 7b | Payer isn't in the split | ✅ 3/3 | 16.6 | 35,364 |
| `ex8_overspend_advice` | Example 8 | Overspend advice | ✅ 3/3 | 12.8 | 32,952 |
| `ex9_refund` | Example 9 | Refunds | ✅ 3/3 | 12.1 | 30,120 |

Reproduce: `.venv/bin/python scripts/eval_report.py` (transcripts in `tests/out/`).
