"""Offline: replay the tool calls and replies from examples.md against every backend.

Runs against the in-memory fake, the Django database backend, and the HTTP API
(through Django's test client). If the fake passes but Django or HTTP fails,
the real backend has drifted from the contract.
"""

import pytest

from agent.scenarios import load_scenarios, run_scenario

SCENARIOS = load_scenarios()


@pytest.mark.parametrize("scn", SCENARIOS, ids=[s["file"].removesuffix(".yaml") for s in SCENARIOS])
def test_golden_replay(scn, any_backend):
    if scn.get("skip"):
        pytest.skip(scn["skip"])
    fails = run_scenario(scn, backend=any_backend)
    assert not fails, "\n".join(fails)
