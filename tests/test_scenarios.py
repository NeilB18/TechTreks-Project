"""Live: run every example scenario against Qwen. Costs API credits.

    pytest -m live                      # all scenarios once
    pytest -m live --repeat 3           # catch flaky behavior
    pytest -m live -k ex7b              # one scenario

Transcripts (tool calls, replies, failures) land in tests/out/<scenario>-<run>.json.
"""

import pytest

from agent.runner import TripAgent
from agent.scenarios import load_scenarios, run_scenario

SCENARIOS = load_scenarios()


def pytest_generate_tests(metafunc):
    if "run" in metafunc.fixturenames:
        metafunc.parametrize("run", range(1, metafunc.config.getoption("repeat") + 1))


@pytest.mark.live
@pytest.mark.parametrize("scn", SCENARIOS, ids=[s["file"].removesuffix(".yaml") for s in SCENARIOS])
def test_live_scenario(scn, run):
    if scn.get("skip"):
        pytest.skip(scn["skip"])
    name = f"{scn['file'].removesuffix('.yaml')}-{run}"
    fails = run_scenario(scn, agent_factory=TripAgent, dump_name=name)
    assert not fails, "\n".join(fails) + f"\n(transcript: tests/out/{name}.json)"
