"""Every example in examples.md has a scenario file (or an explicit skip), and vice versa."""

import re

from agent.scenarios import ROOT, load_scenarios


def test_every_example_has_a_scenario():
    text = (ROOT / "examples.md").read_text()
    examples = set(re.findall(r"^## Example (\w+) —", text, re.M))
    scenarios = {str(s["example"]) for s in load_scenarios()}
    assert examples - scenarios == set(), f"examples without a scenario: {sorted(examples - scenarios)}"
    assert scenarios - examples == set(), f"scenarios for unknown examples: {sorted(scenarios - examples)}"
