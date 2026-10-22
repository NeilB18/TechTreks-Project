"""Load the repo's .env file (gitignored) into os.environ.

Keeps secrets like DASHSCOPE_API_KEY out of the code and out of shell history.
Values already set in the environment win, so a one-off `export` still overrides.
"""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        key = key.strip()
        value = value.split(" #", 1)[0].strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value
