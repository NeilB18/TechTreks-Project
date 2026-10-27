"""Run every scenario against live Qwen N times and write docs/eval-report.md.

    .venv/bin/python scripts/eval_report.py                 # all scenarios, 3 runs each
    .venv/bin/python scripts/eval_report.py --repeat 1 -k edge_
    .venv/bin/python scripts/eval_report.py --from-transcripts   # rebuild the report from tests/out/

Costs API credits (qwen3.8-flash). Transcripts land in tests/out/<scenario>-<run>.json.
"""

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import config  # noqa: E402
from agent import scenarios as scenario_module  # noqa: E402
from agent.scenarios import OUT_DIR, load_scenarios, run_scenario  # noqa: E402

REPORT = ROOT / "docs" / "eval-report.md"


def run_one(scn: dict, run: int) -> str:
    from agent.runner import TripAgent
    name = f"{scn['file'].removesuffix('.yaml')}-{run}"
    for attempt in (1, 2):  # a dropped connection gets one fresh retry of the whole scenario
        try:
            run_scenario(scn, agent_factory=TripAgent, dump_name=name)
            return name
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{name}.json").write_text(json.dumps(
        [{"turn": 0, "failures": [f"run crashed: {error}"], "seconds": 0, "tokens": {}, "model_calls": 0}]))
    return name


def summarize(scenarios: list[dict], repeat: int) -> list[dict]:
    rows = []
    for scn in scenarios:
        stem = scn["file"].removesuffix(".yaml")
        runs = sorted(OUT_DIR.glob(f"{stem}-*.json"))[:repeat]
        if not runs:
            continue
        passed, crashed, reasons, seconds, tokens, turns = 0, 0, Counter(), [], [], 0
        for path in runs:
            transcript = json.loads(path.read_text())
            fails = [f for t in transcript for f in t.get("failures", [])]
            if any(f.startswith("run crashed") for f in fails):
                crashed += 1  # never reached the agent (network/API), so it says nothing about behavior
            passed += not fails
            reasons.update(f[:160] for f in fails)
            for t in transcript:
                turns += 1
                seconds.append(t.get("seconds", 0))
                tokens.append((t.get("tokens") or {}).get("total_tokens", 0))
        rows.append({
            "scenario": stem, "kind": "edge case" if scn.get("kind") == "edge" else f"Example {scn.get('example')}",
            "title": scn.get("title", ""), "runs": len(runs), "passed": passed, "crashed": crashed,
            "avg_seconds": sum(seconds) / max(len(seconds), 1), "avg_tokens": sum(tokens) / max(len(tokens), 1),
            "reasons": reasons.most_common(3)})
    return rows


def write_report(rows: list[dict]) -> str:
    total = sum(r["runs"] for r in rows)
    passed = sum(r["passed"] for r in rows)
    crashed = sum(r["crashed"] for r in rows)
    perfect = sum(r["passed"] == r["runs"] for r in rows)
    lines = [
        "# Agent eval report", "",
        f"- **Model:** `{config.MODEL}` (thinking {'on' if config.ENABLE_THINKING else 'off'})",
        f"- **Date:** {date.today().isoformat()}",
        f"- **Runs:** {total} ({len(rows)} scenarios)",
        f"- **Overall:** {passed}/{total} runs passed ({passed / max(total, 1):.0%}); "
        f"{perfect}/{len(rows)} scenarios passed every run"
        + (f"; {crashed} runs never reached the model (network/API errors)" if crashed else ""), "",
        "Each run plays a scenario's chat messages to the agent against a fresh fake trip, then checks "
        "what it did (tool calls, who it messaged, what changed) and that no budget leaked into the group.", "",
        "| Scenario | Source | What it checks | Passed | Avg sec / turn | Avg tokens / turn |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r["passed"] / r["runs"], r["scenario"])):
        mark = "✅" if r["passed"] == r["runs"] else "⚠️"
        lines.append(f"| `{r['scenario']}` | {r['kind']} | {r['title']} | {mark} {r['passed']}/{r['runs']} "
                     f"| {r['avg_seconds']:.1f} | {r['avg_tokens']:,.0f} |")
    failing = [r for r in rows if r["reasons"]]
    if failing:
        lines += ["", "## What went wrong", ""]
        for r in failing:
            lines.append(f"**`{r['scenario']}`** ({r['passed']}/{r['runs']})")
            lines += [f"- {reason} ({n}×)" for reason, n in r["reasons"]]
            lines.append("")
    lines += ["", "Reproduce: `.venv/bin/python scripts/eval_report.py` (transcripts in `tests/out/`)."]
    text = "\n".join(lines) + "\n"
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(text)
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("-k", default="", help="only scenarios whose file name contains this (comma-separated for several)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--from-transcripts", action="store_true", help="don't call the model; just rebuild the report")
    ap.add_argument("--out-dir", help="where transcripts go (default tests/out); use one per experiment")
    ap.add_argument("--report", help="report path (default docs/eval-report.md)")
    args = ap.parse_args()
    global OUT_DIR, REPORT
    if args.out_dir:
        OUT_DIR = scenario_module.OUT_DIR = Path(args.out_dir).resolve()
    if args.report:
        REPORT = Path(args.report).resolve()

    keys = [k for k in args.k.split(",") if k] or [""]
    scenarios = [s for s in load_scenarios() if not s.get("skip") and any(k in s["file"] for k in keys)]
    if not args.from_transcripts:
        for s in scenarios:  # start clean so old runs don't mix in
            for old in OUT_DIR.glob(f"{s['file'].removesuffix('.yaml')}-*.json"):
                old.unlink()
        jobs = [(s, run) for s in scenarios for run in range(1, args.repeat + 1)]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, name in enumerate(pool.map(lambda j: run_one(*j), jobs), 1):
                print(f"[{i}/{len(jobs)}] {name}", flush=True)
    text = write_report(summarize(scenarios, args.repeat))
    print(text.split("| Scenario")[0])
    print(f"Report: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
