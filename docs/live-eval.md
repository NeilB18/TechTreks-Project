# Live eval: the planning cut (for Romir)

Runs the chat scenarios against real Qwen after the planning cut (Nov 12, 2026): the bot no longer suggests or looks up places, and it has 5 fewer tools. It checks the new calendar flows and that the money flows didn't regress after the prompt changes. You can hand this file to Claude Code and say "run this".

Nothing here changes code. The only outside calls are to Qwen.

## 1. Setup

1. Check out the latest code: `git fetch && git checkout main && git pull` (with the planning cut merged).
2. Python env: `python -m venv .venv`, then install with `.venv/bin/pip install -r requirements.txt` (Windows: `.venv\Scripts\pip install -r requirements.txt`).
3. `.env` in the repo root (copy `.env.example`) needs `DASHSCOPE_API_KEY` and `QWEN_BASE_URL`, from the same Alibaba region. Nothing else is needed for this.
4. On Windows, set `PYTHONUTF8=1` first, or reading the scenario files fails with a `charmap` error.
5. Sanity check, no model calls: `python -m pytest -q` should end in `passed` with no failures.

## 2. Run

Two runs, each into its own folder so they don't mix. With 4 workers each takes about 10–20 minutes.

```bash
# Planning scenarios, 3 times each (21 runs): catches flaky behavior in the calendar flows
python scripts/eval_report.py --repeat 3 -k edge_plan,edge_lodging,edge_no_place_lookups --out-dir tests/out/planning --report docs/eval-report-planning.md

# Everything else once (29 runs): checks the money flows didn't regress
python scripts/eval_report.py --repeat 1 -x edge_plan,edge_lodging,edge_no_place_lookups --out-dir tests/out/rest --report docs/eval-report-rest.md
```

Cost: about 30,000 Qwen tokens per chat turn, so roughly 3–4 million tokens for both runs. If something looks wrong early (every run failing, auth errors), stop and report it rather than finishing the run.

## 3. Send the results back

Commit the two reports and the transcripts on a new branch and push it. `tests/out/` is gitignored, so add it with `-f`:

```bash
git checkout -b live-eval-results/romir
git add docs/eval-report-planning.md docs/eval-report-rest.md
git add -f tests/out/planning tests/out/rest
git commit -m "Live eval results for the planning cut"
git push -u origin live-eval-results/romir
```

Then tell Roger the branch is up. Don't fix anything: the failures are what we need to see, with the transcripts behind them.

## What the planning scenarios check

| Scenario | The bot should |
|---|---|
| `edge_plan_one_step_at_a_time` | Add one thing to one day with no made-up time, put something with no day on the ideas list, answer questions without saving, stay quiet without a mention |
| `edge_plan_idea_to_day` | Put an idea on a day using the idea, so it leaves the list |
| `edge_plan_shared_slot` | Save a named slot ("Sunday lunch"), next to another plan in the same slot, without asking |
| `edge_plan_same_time` | Ask "are you sure?" before putting two plans at exactly the same clock time, then save on a yes |
| `edge_plan_remove_important` | Ask before removing an important activity; remove a plain one right away |
| `edge_lodging` | Save where the group is staying as written, and take a correction |
| `edge_no_place_lookups` | Say in one short line that it doesn't look up places, for "pizza near us?" and "plan our Wednesday", and make nothing up |
