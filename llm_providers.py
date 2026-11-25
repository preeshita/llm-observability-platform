"""
LLM provider layer for the LLM Observability Platform.

The /ask endpoint talks to a provider object instead of a hardcoded model.
Which provider is used is chosen with the LLM_PROVIDER environment variable:

    LLM_PROVIDER=mock     (default) - the original mocked response, no model needed
    LLM_PROVIDER=ollama             - a local model served by Ollama

Every provider returns an LLMResult, so main.py does not need to know
which provider produced the answer.
"""

import os
import time
from dataclasses import dataclass

import httpx


DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant for software engineering, monitoring and DevOps. "
    "Answer clearly and concisely."
)


@dataclass
class LLMResult:
    answer: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    # True when token counts are estimated from text length,
    # False when the provider/runtime reported them.
    tokens_estimated: bool


class LLMProviderError(Exception):
    """Raised when the LLM provider fails (unreachable, bad response, etc.)."""


class LLMProviderTimeout(LLMProviderError):
    """Raised when the LLM provider does not answer within the timeout."""


def estimate_tokens(text: str) -> int:
    """Rough estimate: about 4 characters per token (minimum 1)."""
    return max(1, len(text) // 4)


class MockProvider:
    """The original mocked behaviour. Used by default and in CI."""

    name = "mock"
    model = "mock-model"

    def generate(self, question: str) -> LLMResult:
        time.sleep(0.1)
        answer = f"This is a mock AI response to: {question}"
        return LLMResult(
            answer=answer,
            provider=self.name,
            model=self.model,
            input_tokens=estimate_tokens(question),
            output_tokens=estimate_tokens(answer),
            tokens_estimated=True,
        )


class OllamaProvider:
    """Calls a local Ollama server through its /api/chat endpoint."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt
        # A client can be injected in tests; normally we create our own.
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def generate(self, question: str) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question},
            ],
            "stream": False,
        }

        try:
            response = self.client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMProviderTimeout(
                f"Ollama did not respond within {self.timeout_seconds} seconds"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"Could not reach Ollama at {self.base_url}: {exc}"
            ) from exc
        except ValueError as exc:
            raise LLMProviderError("Ollama returned a response that is not valid JSON") from exc

        answer = (data.get("message") or {}).get("content", "").strip()
        if not answer:
            raise LLMProviderError("Ollama returned an empty answer")

        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        tokens_estimated = input_tokens is None or output_tokens is None

        return LLMResult(
            answer=answer,
            provider=self.name,
            model=data.get("model", self.model),
            input_tokens=input_tokens if input_tokens is not None else estimate_tokens(question),
            output_tokens=output_tokens if output_tokens is not None else estimate_tokens(answer),
            tokens_estimated=tokens_estimated,
        )


def get_provider():
    """Create the provider selected by the LLM_PROVIDER environment variable."""
    provider_name = os.getenv("LLM_PROVIDER", "mock").strip().lower()

    if provider_name == "mock":
        return MockProvider()

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")),
            system_prompt=os.getenv("LLM_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{provider_name}'. Use 'mock' or 'ollama'."
    )
