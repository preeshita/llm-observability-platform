import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langfuse import observe
from llm_providers import (
    LLMProviderError,
    LLMProviderTimeout,
    LLMResult,
    get_provider,
)
from dotenv import load_dotenv
load_dotenv()


from prometheus_client import (
    Counter,
    Histogram,
    make_asgi_app
)

app = FastAPI(
    title="LLM Observability Platform",
    description="AI API with performance monitoring",
    version="1.0.0"
)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "llm_requests_total",
    "Total number of LLM API requests",
    ["status"]
)
LATENCY_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0,
    2.5, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0
)

REQUEST_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "Time taken to process LLM requests",
    buckets=LATENCY_BUCKETS
)

TOKEN_COUNT = Counter(
    "llm_tokens_total",
    "Total tokens processed",
    ["token_type"]
)

ERROR_COUNT = Counter(
    "llm_errors_total",
    "Total number of LLM API errors"
)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@app.get("/")
def home():
    return {
        "message": "LLM Observability Platform is running!"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# The LLM provider is chosen once at startup from the LLM_PROVIDER
# environment variable ("mock" by default, or "ollama").
provider = get_provider()


@observe(name="llm-response", as_type="generation")
def generate_llm_response(question: str) -> LLMResult:
    return provider.generate(question)


@app.post("/ask")
def ask(payload: Question):
    start_time = time.perf_counter()

    try:
        # Generate the response and capture it in Langfuse
        result = generate_llm_response(payload.question)

    except LLMProviderTimeout:
        REQUEST_COUNT.labels(status="error").inc()
        ERROR_COUNT.inc()
        raise HTTPException(
            status_code=504,
            detail="LLM provider timed out"
        )

    except LLMProviderError:
        REQUEST_COUNT.labels(status="error").inc()
        ERROR_COUNT.inc()
        raise HTTPException(
            status_code=502,
            detail="LLM provider request failed"
        )

    except Exception:
        REQUEST_COUNT.labels(status="error").inc()
        ERROR_COUNT.inc()
        raise HTTPException(
            status_code=500,
            detail="Request processing failed"
        )

    latency = time.perf_counter() - start_time

    REQUEST_COUNT.labels(status="success").inc()
    REQUEST_LATENCY.observe(latency)

    TOKEN_COUNT.labels(token_type="input").inc(result.input_tokens)
    TOKEN_COUNT.labels(token_type="output").inc(result.output_tokens)

    return {
        "answer": result.answer,
        "model": result.model,
        "provider": result.provider,
        "latency_ms": round(latency * 1000, 2),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "total_tokens": result.input_tokens + result.output_tokens,
        "tokens_estimated": result.tokens_estimated
    }


# Expose Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)