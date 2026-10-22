#!/usr/bin/env python
import os
import sys
from pathlib import Path

# The agent package lives at the repo root; the backend reuses its rules and contract.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tripapi.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
