# TechTreks

Group-trip agent for a GroupMe chat: plans the trip, logs and splits expenses, gives travel tips by budget, and keeps private per-person budgets on track. Design lives in [specs.md](specs.md) and [examples.md](examples.md).

## Agent (Phase 1–2)

```
agent/
  config.py                 model (qwen3.8-max), thinking, endpoint
  prompts/system_prompt.md  system prompt v1
  tools/schemas.py          20 backend tools + send_message
  backend/protocol.py       the agent <-> backend contract
  backend/fake/             in-memory data model + FakeBackend (placeholder rules in rules.py)
  runner.py                 Qwen function-calling loop for one chat message
  scenarios.py              runs + checks the examples.md scenarios
  cli.py                    fake multi-person chat
tests/
  scenarios/*.yaml          one per example in examples.md
```

Setup:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Offline tests (no API key, free):

```bash
.venv/bin/pytest
```

Live tests against Qwen (costs credits; transcripts go to `tests/out/`). The team key is from the US (Virginia) region, and its endpoint needs your Model Studio workspace ID from the console:

```bash
export DASHSCOPE_API_KEY=...        # Model Studio API key (US region)
export QWEN_WORKSPACE_ID=...        # or QWEN_BASE_URL=<full compatible-mode/v1 URL>
.venv/bin/pytest -m live
.venv/bin/pytest -m live --repeat 3 -k ex7b
```

Chat with the agent by hand:

```bash
DASHSCOPE_API_KEY=... QWEN_WORKSPACE_ID=... .venv/bin/python -m agent.cli tests/scenarios/ex1_dropout.yaml
```

Then type `priya: @tripbot I can't make it anymore`, or `mia dm: lower my budget to $500`.

## Placeholders

- Budget warnings: remaining < 10% (`agent/backend/fake/rules.py`). The real logic is still TBD, so Examples 3 and 8 are skipped.
- FX: fixed rate table in `rules.py`. The provider is still TBD.
- Travel tips and itineraries: canned text in the fake backend. Google Places and SerpAPI come later.
