import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_addoption(parser):
    parser.addoption("--repeat", type=int, default=1,
                     help="Run each live scenario N times to catch flaky behavior")
