"""Agent settings. Change the model or endpoint here only."""

import os

# Qwen via Alibaba Cloud Model Studio's OpenAI-compatible API.
MODEL = "qwen3.8-max"
ENABLE_THINKING = True  # Qwen3 thinking mode; tool_choice must stay "auto" while it's on
MAX_TOOL_ROUNDS = 15  # model calls per incoming chat message

# API keys are bound to the region they were created in. The team key is US (Virginia),
# whose endpoint includes the Model Studio workspace ID from the console.
API_KEY_ENV = "DASHSCOPE_API_KEY"
US_BASE_URL = "https://{workspace_id}.us-east-1.maas.aliyuncs.com/compatible-mode/v1"


def base_url() -> str:
    """QWEN_BASE_URL overrides everything; otherwise build the US URL from QWEN_WORKSPACE_ID."""
    if os.environ.get("QWEN_BASE_URL"):
        return os.environ["QWEN_BASE_URL"]
    workspace_id = os.environ.get("QWEN_WORKSPACE_ID")
    if not workspace_id:
        raise RuntimeError("Set QWEN_WORKSPACE_ID (Model Studio console, US region) or QWEN_BASE_URL")
    return US_BASE_URL.format(workspace_id=workspace_id)


# Seed for the fake backend's random leftover-cent assignment, so tests are repeatable.
RNG_SEED = 7
