"""The one model every agent uses: gpt-6-luna, routed through Portkey.

Uses the OpenAI Responses API (/v1/responses): gpt-6-luna's deployment rejects function
tools on /v1/chat/completions while reasoning is on.
"""
from __future__ import annotations

import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from core.config import MAX_OUTPUT_TOKENS, MODEL, REASONING_EFFORT, PORTKEY_BASE_URL, PORTKEY_PROVIDER


def build_model() -> OpenAIResponsesModel:
    key = os.environ.get("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Put it in your environment or in .env next to README.md.")
    headers = {"x-portkey-api-key": key}
    if PORTKEY_PROVIDER:
        headers["x-portkey-provider"] = PORTKEY_PROVIDER
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key, default_headers=headers, max_retries=2)
    settings = OpenAIResponsesModelSettings(max_tokens=MAX_OUTPUT_TOKENS, openai_reasoning_effort=REASONING_EFFORT)
    return OpenAIResponsesModel(MODEL, provider=OpenAIProvider(openai_client=client), settings=settings)
