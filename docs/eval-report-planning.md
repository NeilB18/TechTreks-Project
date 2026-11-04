# Agent eval report

- **Model:** `qwen3.8-flash` (thinking on)
- **Date:** 2026-11-03
- **Runs:** 36 (12 scenarios)
- **Overall:** 32/36 runs passed (89%); 10/12 scenarios passed every run

Each run plays a scenario's chat messages to the agent against a fresh fake trip, then checks what it did (tool calls, who it messaged, what changed) and that no budget leaked into the group.

| Scenario | Source | What it checks | Passed | Avg sec / turn | Avg tokens / turn |
|---|---|---|---|---|---|
| `edge_itinerary_needs_leader` | edge case | Saving an itinerary waits for the leader when itinerary saves are routed to them | ⚠️ 0/3 | 29.0 | 39,648 |
| `edge_plan_edit_draft` | edge case | Draft edits change one stop without rebuilding; a saved stop can be removed | ⚠️ 2/3 | 13.2 | 44,647 |
| `edge_lodging` | edge case | Where we're staying is saved from chat, confirmed with its address, and corrected by anyone | ✅ 3/3 | 9.7 | 42,548 |
| `edge_lodging_not_found` | edge case | A lodging the map can't find isn't saved, and the bot asks for the street address | ✅ 3/3 | 11.9 | 42,931 |
| `edge_nearby` | edge case | Nearby search uses the saved lodging, gives closest places with distances, and asks when there's no lodging | ✅ 3/3 | 13.9 | 45,527 |
| `edge_nearby_no_lodging` | edge case | Nearby search with no lodging saved asks where the group is staying, saves it, then searches | ✅ 3/3 | 10.6 | 38,501 |
| `edge_plan_day_full` | edge case | Adding a meal to a day whose meal slots are taken saves nothing and asks | ✅ 3/3 | 14.7 | 44,546 |
| `edge_plan_idea_to_day` | edge case | Putting an idea on a day uses the idea and takes it off the ideas list | ✅ 3/3 | 13.3 | 43,585 |
| `edge_plan_one_step_at_a_time` | edge case | One place stays one place; a place with no day goes on the ideas list; questions and chatter save nothing | ✅ 3/3 | 9.6 | 35,268 |
| `edge_plan_place_not_found` | edge case | A place the map can't find is added but flagged, and the bot asks if the name is right | ✅ 3/3 | 16.5 | 47,821 |
| `edge_plan_remove_important` | edge case | Removing an activity marked important waits for a yes; a plain one goes right away | ✅ 3/3 | 7.6 | 33,647 |
| `edge_plan_vague_ask_gets_which_days` | edge case | A vague itinerary ask gets "which days?" first, then a draft for only that day that uses the group's ideas | ✅ 3/3 | 14.1 | 35,186 |

## What went wrong

**`edge_itinerary_needs_leader`** (0/3)
- missing call generate_itinerary with {}; got none (3×)
- expected 10 activities, have 12 (1×)
- message to group missing 'Aarav': "On it, @Jake — that'd be Mar 14–18 (5 days). Quick one before I draft: chill mornings or packed days, and any must-dos you gu (1×)

**`edge_plan_edit_draft`** (2/3)
- missing call remove_activity with {}; got none (1×)
- expected 2 activities, have 3 (1×)


Reproduce: `.venv/bin/python scripts/eval_report.py` (transcripts in `tests/out/`).
