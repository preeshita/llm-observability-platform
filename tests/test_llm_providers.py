"""
Tests for the LLM provider layer.

These tests never call a real Ollama server. Ollama's HTTP responses are
simulated with httpx.MockTransport, so the tests also run in GitHub Actions.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from llm_providers import (
    LLMProviderError,
    LLMProviderTimeout,
    MockProvider,
    OllamaProvider,
    get_provider,
)


def make_ollama(handler) -> OllamaProvider:
    """Build an OllamaProvider whose HTTP calls go to a fake handler."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaProvider(
        base_url="http://fake-ollama:11434",
        model="llama3.2:3b",
        timeout_seconds=5,
        client=client,
    )


# ---------- Provider selection ----------

def test_default_provider_is_mock(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert isinstance(get_provider(), MockProvider)


def test_ollama_provider_selected_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:1b")
    provider = get_provider()
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llama3.2:1b"


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "does-not-exist")
    with pytest.raises(ValueError):
        get_provider()


# ---------- Ollama provider ----------

def test_ollama_success_uses_reported_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={
            "model": "llama3.2:3b",
            "message": {"role": "assistant", "content": "Prometheus collects metrics."},
            "prompt_eval_count": 46,
            "eval_count": 75,
        })

    result = make_ollama(handler).generate("What is Prometheus?")

    assert result.answer == "Prometheus collects metrics."
    assert result.provider == "ollama"
    assert result.model == "llama3.2:3b"
    assert result.input_tokens == 46
    assert result.output_tokens == 75
    assert result.tokens_estimated is False


def test_ollama_sends_system_prompt():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "message": {"content": "ok"},
            "prompt_eval_count": 1,
            "eval_count": 1,
        })

    make_ollama(handler).generate("hello")

    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user"]
    assert captured["body"]["stream"] is False


def test_ollama_missing_token_counts_fall_back_to_estimate():
    def handler(request):
        return httpx.Response(200, json={"message": {"content": "An answer"}})

    result = make_ollama(handler).generate("A question")
    assert result.tokens_estimated is True
    assert result.input_tokens > 0
    assert result.output_tokens > 0


def test_ollama_timeout_raises_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMProviderTimeout):
        make_ollama(handler).generate("hello")


def test_ollama_unreachable_raises_provider_error():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(LLMProviderError):
        make_ollama(handler).generate("hello")


def test_ollama_http_error_raises_provider_error():
    def handler(request):
        return httpx.Response(404, json={"error": "model not found"})

    with pytest.raises(LLMProviderError):
        make_ollama(handler).generate("hello")


def test_ollama_empty_answer_raises_provider_error():
    def handler(request):
        return httpx.Response(200, json={"message": {"content": ""}})

    with pytest.raises(LLMProviderError):
        make_ollama(handler).generate("hello")


# ---------- /ask endpoint error handling ----------

class _FailingProvider:
    def __init__(self, error):
        self.error = error

    def generate(self, question):
        raise self.error


def test_ask_returns_504_on_provider_timeout(monkeypatch):
    monkeypatch.setattr(main, "provider", _FailingProvider(LLMProviderTimeout("slow")))
    response = TestClient(main.app).post("/ask", json={"question": "hi"})
    assert response.status_code == 504


def test_ask_returns_502_on_provider_error(monkeypatch):
    monkeypatch.setattr(main, "provider", _FailingProvider(LLMProviderError("down")))
    response = TestClient(main.app).post("/ask", json={"question": "hi"})
    assert response.status_code == 502



# ---------- Latency histogram buckets ----------

def test_latency_histogram_has_long_llm_buckets():
    client = TestClient(main.app)
    client.post("/ask", json={"question": "bucket check"})
    text = client.get("/metrics").text
    # SLO dashboard depends on this exact bucket label
    assert 'llm_request_latency_seconds_bucket{le="1.0"}' in text
    # New buckets for slow local LLM responses
    assert 'llm_request_latency_seconds_bucket{le="30.0"}' in text
    assert 'llm_request_latency_seconds_bucket{le="120.0"}' in text