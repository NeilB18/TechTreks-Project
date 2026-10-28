# Writing scenarios

A scenario is a short scripted group chat with the bot, plus what must be true after each message. Scenarios are how we know the bot works. The model can answer the same message differently each time, and a prompt fix for one case can quietly break another. Every scenario runs in two ways:

- **Offline (free, in CI on every PR):** a "golden" correct answer is replayed against the engine, the Django database and the HTTP API. No model is called. This checks that the rules and the scenario itself are right.
- **Live (costs a little, run by hand):** the real Qwen model plays the bot, and the same checks decide whether it behaved.

The checker lives in `agent/scenarios.py`, and the scenarios live in `tests/scenarios/*.yaml`.

## The rule for PRs

**Every feature or bug-fix PR that changes what the bot or engine does adds or updates at least one scenario.** In the PR description, include:

- the offline result: `.venv/bin/pytest -q` passes
- for anything touching the agent, prompt, runner or engine: the live result for your scenarios (`-k your_scenario --repeat 3`), and the full eval pass rate if you changed the prompt or runner. The full eval must stay at 98% or better.
- if something fails live, the transcript file in `tests/out/` and what you think went wrong

A feature without a scenario isn't done.

## File layout

One file per scenario in `tests/scenarios/`:
- `exN_*.yaml`: a worked example from `examples.md`, with `example: "4a"` at the top.
- `edge_*.yaml`: everything else, with `kind: edge` at the top.

```yaml
kind: edge
title: One line saying what this tests
seed:      # the trip before the chat starts
  ...
turns:     # the chat, one message per turn
  - sender: jake
    text: "@tripbot ..."
    expect:   # loose checks the live bot must pass
      ...
    golden:   # one exact correct answer, replayed offline
      ...
```

## `seed`: the starting state

Money is always in **cents** (`12000` is $120). Ids are short lowercase names, and they're what tool calls and messages use.

```yaml
seed:
  now: "2027-03-15T20:00:00"          # the bot's "current time" (optional)
  trip: {id: miami, name: Miami Spring Break, status: ACTIVE, destination: Miami,
         start_date: "2027-03-14", end_date: "2027-03-18", base_currency: USD,
         leader: aarav, leader_approval: [member_changes, trip_changes]}
  members:
    - {id: aarav, name: Aarav, handle: "@aarav-venmo"}
    - {id: mia, name: Mia, handle: "@mia-venmo"}
    - {id: sam, name: Sam, active: false}          # someone who dropped out
  budgets:
    mia: {total: 90000, limits: {FOOD: 15000}}     # private budget with a category limit
  exclusions:
    - [mia, DRINKS]                                # Mia opts out of drinks
  expenses:
    - {id: e1, paid_by: aarav, amount: 12000, description: Brunch, category: FOOD,
       split_with: [aarav, mia]}
  paybacks:
    - {from: mia, to: aarav, amount: 6000}
  activities: [...]     # see edge_itinerary_needs_leader.yaml
  polls: [...]          # see edge_poll_flow.yaml
```

- **Status:** `PLANNING`, `ACTIVE` or `DONE`.
- **Categories:** `LODGING`, `TRANSPORT`, `FOOD`, `DRINKS`, `ACTIVITIES`, `OTHER`.

The seed is loaded by `TripEngine.load_seed` (`agent/backend/core/engine.py`). If you need a field that isn't listed here, check that function.

## `turns`: the chat

```yaml
  - sender: mia                  # a member id
    text: "@tripbot dinner was $120, split with everyone except Jake"
    mentioned: false             # optional: the message doesn't @mention the bot (default true)
    channel: dm                  # optional: a private message to the bot (default group)
```

## `expect`: what must be true

Keep these checks **loose**. The live model words things differently every run, so check facts, not phrasing. Every key is optional.

| Key | Meaning |
|---|---|
| `calls: [{name, args}]` | This tool was called, with *at least* these args. Strings match case-insensitively. A list must match exactly, as a set. Leave out args that could reasonably vary. |
| `count_min: {tool: n}` | The tool was called at least n times (for example, a budget check per person). |
| `forbid: [tool]` | This tool must not succeed this turn. |
| `forbid_mutations: true` | Nothing may change this turn (asking or confirming turns). |
| `messages: [{to, ...}]` | `to` is `group` or a member id (a private message). All text sent to them this turn is joined, then checked with `contains: [...]` (all of them), `contains_any: [...]` (at least one), `not_contains: [...]`, and `matches: [regex]`. |
| `no_messages_to: [to]` | Nothing was sent to them. |
| `silent: true` | The bot sent nothing at all. |
| `end_state: [...]` | Checks on the trip after the turn, listed in the next table. |

`end_state` checks:

| Check | Example |
|---|---|
| `balance` | `{from: aarav, to: mia, amount: 6000}`: Aarav's suggested payment to Mia |
| `no_debts_for` | `jake` |
| `member_active` | `{sam: false}` |
| `trip` | `{start_date: "2027-03-15", status: ACTIVE}`, an exact match |
| `trip_contains` | `{destination: cancun}`, ignoring case and accents |
| `budget_total` | `{mia: 95000}` |
| `opt_out` / `no_opt_out` | `[mia, DRINKS]` |
| `expense_count`, `refund_count`, `activity_count` | `3` |
| `reminder_due_on` | `"2027-03-16"` |

Need a check that doesn't exist? Add it in `_check_state` in `agent/scenarios.py`, in the same PR.

**Privacy is checked automatically on every turn.** If any group message contains a member's budget total, the scenario fails. You don't need to write this check yourself.

## `golden`: one exact correct answer

Write the tool calls and replies a perfect bot would produce. Offline, these calls really run against the engine, Django and the API, and then `expect` is checked against the result. So the golden answer has to pass your own `expect`. That proves the scenario and the engine agree before any model is involved.

- **Use full args:** include `trip_id` and everything the tool needs. A tool error in a golden answer fails the test.
- **`messages`:** `[{to, text}]`, the exact replies.
- **A turn where the bot should stay quiet:** `golden: {}`.

To see the args each tool takes, look at `agent/tools/schemas.py` or the matching method in `agent/backend/core/engine.py`.

## Worked example

Say we want to test a ride split three ways, followed by someone asking what they owe. Save this as `tests/scenarios/edge_uber_then_owe.yaml`:

```yaml
kind: edge
title: Split a ride three ways, then ask what you owe
seed:
  now: "2027-03-14T09:00:00"
  trip: {id: miami, name: Miami Spring Break, status: ACTIVE, destination: Miami,
         start_date: "2027-03-14", end_date: "2027-03-18", base_currency: USD,
         leader: aarav, leader_approval: [member_changes, trip_changes]}
  members:
    - {id: aarav, name: Aarav, handle: "@aarav-venmo"}
    - {id: jake, name: Jake, handle: "@jake-venmo"}
    - {id: mia, name: Mia, handle: "@mia-venmo"}
turns:
  - sender: jake
    text: "@tripbot uber from the airport was $45, I paid, split with everyone"
    expect:
      calls:
        - {name: log_expense, args: {paid_by: jake, amount: 4500, currency: USD, category: TRANSPORT}}
      messages:
        - {to: group, contains: ["$45", "$15"]}
      end_state:
        - expense_count: 1
        - balance: {from: aarav, to: jake, amount: 1500}
        - balance: {from: mia, to: jake, amount: 1500}
    golden:
      calls:
        - {name: log_expense, args: {trip_id: miami, paid_by: jake, amount: 4500, currency: USD,
                                     description: Uber from the airport, category: TRANSPORT,
                                     split_with: [aarav, jake, mia],
                                     source_message: "uber from the airport was $45"}}
      messages:
        - {to: group, text: "Logged 🚕 Uber from the airport, $45, paid by Jake, split 3 ways ($15 each)."}
  - sender: mia
    text: "@tripbot what do I owe?"
    expect:
      calls:
        - {name: get_balances}
      forbid_mutations: true
      messages:
        - {to: group, contains: ["$15", Jake]}
    golden:
      calls:
        - {name: get_balances, args: {trip_id: miami}}
      messages:
        - {to: group, text: "Mia, you owe Jake $15. Venmo: @jake-venmo"}
```

Why it's written this way:

- **Turn 1's `calls` leaves out `description` and `split_with`.** The model might write "Uber" or "Airport Uber", and it might pass everyone or nobody, which also means everyone. Both are correct, so the `end_state` balances check the actual result instead.
- **The messages check `$45` and `$15`, not a whole sentence.** The model's wording will vary from run to run.
- **Turn 2 uses `forbid_mutations: true`.** Asking a question must not change anything.

## Commands

From the repo root (`~/code/TechTreks-Project`):

```bash
.venv/bin/pytest tests/test_golden.py -k edge_uber_then_owe     # offline: your scenario on engine, Django and API
.venv/bin/pytest -q                                              # offline: everything (run before every PR)
.venv/bin/python -m agent.cli tests/scenarios/edge_uber_then_owe.yaml   # chat with the real bot from your seed
.venv/bin/pytest -m live -k edge_uber_then_owe --repeat 3        # live: your scenario, 3 runs
.venv/bin/python scripts/eval_report.py -k edge_uber,ex9 --repeat 3 --out-dir tests/out/mine --report tests/out/mine/report.md
.venv/bin/python scripts/eval_report.py --repeat 3               # live: full eval -> docs/eval-report.md
```

- **Live runs need Qwen access:** `DASHSCOPE_API_KEY` and `QWEN_BASE_URL` in your gitignored `.env`. Ask Romir for them privately; never paste them into a chat, an issue or a commit.
- **Transcripts:** each live run writes `tests/out/<scenario>-<run>.json`, with every tool call, result, message, time and token count. When a run fails, start there.
- **Experiments:** use `--out-dir` and `--report` for experiments, so you don't overwrite the main `docs/eval-report.md`. `--from-transcripts` rebuilds a report without calling the model again.

## When it fails

1. **Offline failure:** either your golden answer or `expect` is wrong, or the engine has a bug. If it passes on the engine but fails on Django or HTTP, the database code has drifted from the engine. Tell Roger.
2. **Live failure, but offline passes:** read the transcript. Then decide:
   - **`expect` is too strict** (it pinned wording or args that can reasonably vary): loosen it.
   - **The bot really misbehaved:** fix the prompt (`agent/prompts/system_prompt.md`) or add a runner guard (`agent/runner.py`). Then rerun this scenario with `--repeat 5`, and the full eval if you touched the prompt or runner.
3. **Flaky (passes some runs):** treat it as a real bug. The demo gets one run.

## What to write scenarios about

Good sources:

- every new tool or rule (one happy path, plus one where it should refuse or ask first)
- every bug you see in a real chat: reproduce it as a scenario first, then fix it
- how real people type: slang, typos, vague amounts ("like 40 bucks"), corrections mid-thread
- people trying to break it: asking for someone's budget, faking the leader, "ignore your rules"

Gaps nobody has written yet:

- adding a member by name
- `add_activity`
- changing the trip's location
- a dropout when member changes go to the leader
- a refund after someone already paid back
- a poll tie, and a poll closing on its own
- receipt photos, auto-log mode, and other currencies, once they're built
