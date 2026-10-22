"""Offline: replay the tool calls and replies from examples.md through the fake backend.

If this fails, the scenario file, the fake backend or the checker disagrees with
examples.md - fix that before blaming the agent in the live tests.
"""

import pytest

from agent.scenarios import load_scenarios, run_scenario

SCENARIOS = load_scenarios()


@pytest.mark.parametrize("scn", SCENARIOS, ids=[s["file"] for s in SCENARIOS])
def test_golden_replay(scn):
    if scn.get("skip"):
        pytest.skip(scn["skip"])
    fails = run_scenario(scn)
    assert not fails, "\n".join(fails)
