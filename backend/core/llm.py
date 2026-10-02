"""Pluggable LLM client.

Narration is either produced by a real model or not produced at all. With no provider
configured the platform still runs end to end — every metric, ranking, importance and
drift figure is computed by an agent — it simply reports those numbers without prose
rather than pattern-matching a paragraph to sit beside them.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional

from . import config

logger = logging.getLogger(__name__)

# transient upstream states worth a retry: rate limit, high demand, gateway hiccups
_RETRY_STATUS = {429, 500, 502, 503, 504}


class LLMUnavailable(RuntimeError):
    """Transient — worth retrying."""


class LLMPermanent(RuntimeError):
    """Bad key, retired model, malformed request. Retrying cannot help."""


class BaseLLM:
    name = "base"

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        raise NotImplementedError


class NullLLM(BaseLLM):
    """No narrator configured, or the configured one failed.

    Returns nothing rather than pre-written prose. Everything the platform reports is
    computed by a model or an agent; a paragraph that was pattern-matched from the prompt
    is not analysis, and presenting it beside real metrics implies a reading of the data
    that nothing actually performed. Callers omit the narrative section instead.
    """

    name = "none"

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        return ""


class OllamaLLM(BaseLLM):
    name = "ollama"

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        import requests

        resp = requests.post(
            f"{config.OLLAMA_HOST}/api/chat",
            json={
                "model": config.OLLAMA_MODEL,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {"num_predict": max_tokens},
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class OpenAICompatibleLLM(BaseLLM):
    """Groq and OpenRouter both speak the OpenAI chat-completions dialect."""

    def __init__(self, base_url: str, api_key: str, model: str, name: str) -> None:
        if not api_key:
            raise LLMUnavailable(f"{name} selected but no API key set")
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.name = name

    def payload(self, system: str, user: str, max_tokens: int) -> Dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        import requests

        max_tokens = max(max_tokens, config.LLM_MIN_MAX_TOKENS)
        last: Exception = LLMUnavailable(f"{self.name} produced no response")

        for attempt in range(config.LLM_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=self.payload(system, user, max_tokens),
                    timeout=120,
                )
                if resp.status_code in _RETRY_STATUS:
                    raise LLMUnavailable(f"{self.name} HTTP {resp.status_code}")
                if resp.status_code >= 400:
                    # a bad key, a retired model, a malformed body — retrying only wastes the run
                    raise LLMPermanent(f"{self.name} HTTP {resp.status_code}: "
                                       f"{resp.text[:160]}")
                choice = resp.json()["choices"][0]
                message = choice.get("message") or {}
                text = message.get("content") or ""
                if not text.strip():
                    # reasoning models (Nemotron, gpt-oss) put the answer in `reasoning_content`
                    # when the completion budget is spent thinking; better that than no prose
                    text = message.get("reasoning_content") or ""
                if choice.get("finish_reason") == "length":
                    logger.warning("%s truncated at %d tokens — raise DATAID_LLM_MIN_MAX_TOKENS",
                                   self.name, max_tokens)
                if not text.strip():
                    raise LLMUnavailable(f"{self.name} returned an empty completion")
                return text
            except LLMPermanent:
                raise
            except Exception as exc:  # noqa: BLE001 — transient: retry, then give up
                last = exc
                if attempt < config.LLM_RETRIES:
                    time.sleep(1.5 * (attempt + 1))

        raise last


class GeminiLLM(OpenAICompatibleLLM):
    """Google Gemini through its OpenAI-compatible surface.

    Free tier, no billing account required. Sends `reasoning_effort` so 3.x thinking models
    do not spend the whole completion budget before emitting prose.
    """

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__("https://generativelanguage.googleapis.com/v1beta/openai",
                         api_key, model, "gemini")

    def payload(self, system: str, user: str, max_tokens: int) -> Dict[str, Any]:
        body = super().payload(system, user, max_tokens)
        if model_thinks(self.model):
            body["reasoning_effort"] = "low"
        return body


class NvidiaLLM(OpenAICompatibleLLM):
    """NVIDIA build (integrate.api.nvidia.com), OpenAI-compatible.

    Thinking is opt-in *per model*: the nemotron-3 family reasons before answering and needs
    it enabled, while a model served without a reasoning config rejects the same parameters
    with HTTP 500 ("thinking_token_budget is set but reasoning_config is not configured").
    That status is in the retry set, so sending them blindly would burn both retries and drop
    the run to the offline narrator.
    """

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__("https://integrate.api.nvidia.com/v1", api_key, model, "nvidia")

    @property
    def thinking(self) -> bool:
        if config.NVIDIA_THINKING in ("on", "off"):
            return config.NVIDIA_THINKING == "on"
        return bool(re.search(config.NVIDIA_THINKING_MODELS, self.model))

    def payload(self, system: str, user: str, max_tokens: int) -> Dict[str, Any]:
        body = super().payload(system, user, max_tokens)
        if self.thinking:
            budget = max(max_tokens, config.NVIDIA_REASONING_BUDGET)
            body["max_tokens"] = budget
            body["temperature"] = 1
            body["top_p"] = 0.95
            body["chat_template_kwargs"] = {"enable_thinking": True}
            body["reasoning_budget"] = budget
        return body


class HuggingFaceLLM(OpenAICompatibleLLM):
    """Hugging Face Inference Providers router, OpenAI-compatible.

    One token reaches whichever partner (Together, Fireworks, Baseten, DeepInfra,
    Featherless) currently serves the model, so an open-weights model too large to host
    is still a plain chat endpoint here — Kimi K3 is 2.8T parameters and runs nowhere
    local, but costs the same three lines as Groq.

    K3 reasons on every call and offers no switch to stop it, so the completion budget has to
    cover the thinking *and* the prose. The ordinary 2048 floor is not enough — the longer
    narration prompts spend all of it reasoning and come back with `finish_reason="length"` —
    so thinking models get HF_REASONING_BUDGET instead, gated on the model name the way the
    NVIDIA client gates its own. max_tokens is a ceiling, not a target: a short answer still
    costs a short answer.
    """

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__("https://router.huggingface.co/v1", api_key, model, "huggingface")

    @property
    def thinking(self) -> bool:
        return bool(re.search(config.HF_THINKING_MODELS, self.model))

    def payload(self, system: str, user: str, max_tokens: int) -> Dict[str, Any]:
        body = super().payload(system, user, max_tokens)
        if self.thinking:
            body["max_tokens"] = max(max_tokens, config.HF_REASONING_BUDGET)
        return body


def model_thinks(model: str) -> bool:
    """Gemini 3.x reasons by default; 2.x does not and rejects the parameter."""
    return bool(re.match(r"gemini-3", model))


_CLIENT: Optional[BaseLLM] = None


def get_llm() -> BaseLLM:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    provider = config.LLM_PROVIDER.lower()
    try:
        if provider == "ollama":
            _CLIENT = OllamaLLM()
        elif provider == "groq":
            _CLIENT = OpenAICompatibleLLM(
                "https://api.groq.com/openai/v1", config.GROQ_API_KEY, config.GROQ_MODEL, "groq"
            )
        elif provider == "openrouter":
            _CLIENT = OpenAICompatibleLLM(
                "https://openrouter.ai/api/v1",
                config.OPENROUTER_API_KEY,
                config.OPENROUTER_MODEL,
                "openrouter",
            )
        elif provider == "gemini":
            _CLIENT = GeminiLLM(config.GEMINI_API_KEY, config.GEMINI_MODEL)
        elif provider == "nvidia":
            _CLIENT = NvidiaLLM(config.NVIDIA_API_KEY, config.NVIDIA_MODEL)
        elif provider in ("huggingface", "hf"):
            _CLIENT = HuggingFaceLLM(config.HF_TOKEN, config.HF_MODEL)
        else:
            _CLIENT = NullLLM()
    except LLMUnavailable as exc:
        logger.warning("%s unavailable (%s) — narration disabled, metrics unaffected",
                       provider, exc)
        _CLIENT = NullLLM()
    return _CLIENT


def narrate(prompt: str, system: str = "You are dataid, a senior data scientist. Be concise and concrete.") -> str:
    """Never raises, and never invents. Returns "" when no narration could be produced.

    Construction-time failures are caught in get_llm(); this covers call-time ones — a rate
    limit, a 503, a dropped connection — which would otherwise take the whole pipeline down
    partway through an agent. A failure costs the prose only: every metric, ranking and
    explanation around it is computed and stands on its own.
    """
    client = get_llm()
    if isinstance(client, NullLLM):
        return ""
    try:
        return client.complete(system, prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s narration failed (%s) — the section is omitted rather than filled",
                       client.name, exc)
        return ""
