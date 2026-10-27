"""Agent settings. Change the model or endpoint here only."""

import os

from agent.env import load_env

load_env()

# Qwen via Alibaba Cloud Model Studio's OpenAI-compatible API.
MODEL = "qwen3.8-flash"
# Qwen3 thinking mode (tool_choice must stay "auto" while it's on). Thinking is most of the reply time,
# so it can be switched off (QWEN_THINKING=0) or capped (QWEN_THINKING_BUDGET=<tokens>).
ENABLE_THINKING = os.environ.get("QWEN_THINKING", "1") != "0"
THINKING_BUDGET = int(os.environ["QWEN_THINKING_BUDGET"]) if os.environ.get("QWEN_THINKING_BUDGET") else None
# After a reply that only sends messages, the next call (usually just "done", sometimes the remaining DMs)
# runs with thinking off: ~1.5s instead of ~8s. Ending the turn there instead dropped DMs in the eval.
FAST_FOLLOWUP = os.environ.get("QWEN_FAST_FOLLOWUP", "1") != "0"
MAX_TOOL_ROUNDS = 15  # model calls per incoming chat message
REQUEST_TIMEOUT_S = 90  # per model call

# API keys only work on the endpoint of the region they were created in (the team key is
# Singapore). QWEN_BASE_URL is that endpoint: "<API Host from Workspace Management>/compatible-mode/v1".
API_KEY_ENV = "DASHSCOPE_API_KEY"


def base_url() -> str:
    url = os.environ.get("QWEN_BASE_URL")
    if not url:
        raise RuntimeError("Set QWEN_BASE_URL in .env (Model Studio Workspace Management -> API Host)")
    return url


