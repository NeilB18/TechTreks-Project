# Live eval: Track 1 planning (for Romir)

Runs the chat scenarios against real Qwen to check the bot follows the new planning flow (planning PRs #29–#35) and that the money flows didn't regress after the prompt changes. You can hand this file to Claude Code and say "run this".

Nothing here changes code. The scenarios use made-up map data, so the only outside calls are to Qwen.

## 1. Setup

1. Check out the top of the planning stack: `git fetch && git checkout live-eval/roger && git pull`.
2. Python env: `python -m venv .venv`, then install with `.venv/bin/pip install -r requirements.txt` (Windows: `.venv\Scripts\pip install -r requirements.txt`).
3. `.env` in the repo root (copy `.env.example`) needs `DASHSCOPE_API_KEY` and `QWEN_BASE_URL`, from the same Alibaba region. Nothing else is needed for this.
4. On Windows, set `PYTHONUTF8=1` first, or reading the scenario files fails with a `charmap` error.
5. Sanity check, no model calls: `python -m pytest -q` should end in `passed` with no failures.

## 2. Run

Two runs, each into its own folder so they don't mix. With 4 workers each takes about 15–25 minutes.

```bash
# Planning scenarios, 3 times each (36 runs): catches flaky behavior in the new flows
python scripts/eval_report.py --repeat 3 -k edge_plan,edge_lodging,edge_nearby,edge_itinerary --out-dir tests/out/planning --report docs/eval-report-planning.md

# Everything else once (28 runs): checks the money flows didn't regress
python scripts/eval_report.py --repeat 1 -x edge_plan,edge_lodging,edge_nearby,edge_itinerary --out-dir tests/out/rest --report docs/eval-report-rest.md
```

Cost: about 30,000 Qwen tokens per chat turn, so roughly 4–5 million tokens for both runs. If something looks wrong early (every run failing, auth errors), stop and report it rather than finishing the run.

## 3. Send the results back

Commit the two reports and the transcripts on a new branch and push it. `tests/out/` is gitignored, so add it with `-f`:

```bash
git checkout -b live-eval-results/romir
git add docs/eval-report-planning.md docs/eval-report-rest.md
git add -f tests/out/planning tests/out/rest
git commit -m "Live eval results for the planning PRs"
git push -u origin live-eval-results/romir
```

Then tell Roger the branch is up. Don't fix anything: the failures are what we need to see, with the transcripts behind them.

## What the planning scenarios check

| Scenario | The bot should |
|---|---|
| `edge_plan_one_step_at_a_time` | Add one place to one day, put a place with no day on the ideas list, answer questions without saving, stay quiet without a mention |
| `edge_plan_vague_ask_gets_which_days` | Ask "which days?" before drafting, then draft only that day, using the group's ideas |
| `edge_plan_edit_draft` | Change one stop in a draft without rebuilding it, save, then remove a saved stop |
| `edge_plan_idea_to_day` | Put an idea on a day using the idea, so it leaves the list |
| `edge_plan_place_not_found` | Say when the map can't find a place and ask if the name is right |
| `edge_plan_day_full` | Not double-book a full day; ask instead |
| `edge_plan_remove_important` | Ask before removing an important activity; remove a plain one right away |
| `edge_itinerary_needs_leader` | Draft the whole trip when asked, and save only with the leader's OK |
| `edge_lodging` | Save where the group is staying, confirm the address, take a correction |
| `edge_lodging_not_found` | Not save a lodging the map can't find; ask for the street address |
| `edge_nearby` | Give the closest places with distances, from the lodging or a named place |
| `edge_nearby_no_lodging` | Ask where the group is staying, save it, then search |
| `edge_pick_destination` | Ask where the group flies from, compare places against budgets with flight links, then poll |
