"""Agent settings. Change the model or endpoint here only."""

import os

from agent.env import load_env

load_env()

# Qwen via Alibaba Cloud Model Studio's OpenAI-compatible API.
MODEL = "qwen3.8-flash"
ENABLE_THINKING = True  # Qwen3 thinking mode; tool_choice must stay "auto" while it's on
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


