
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langfuse import observe
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

REQUEST_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "Time taken to process LLM requests"
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


@observe(name="mock-llm-response", as_type="generation")
def generate_mock_response(question: str):
    time.sleep(0.1)

    answer = f"This is a mock AI response to: {question}"

    return {
        "answer": answer,
        "input_tokens": max(1, len(question) // 4),
        "output_tokens": max(1, len(answer) // 4)
    }

@app.post("/ask")
def ask(payload: Question):
    start_time = time.perf_counter()

    try:
        # Generate mock response and capture it in Langfuse
        result = generate_mock_response(payload.question)

        answer = result["answer"]
        input_tokens = result["input_tokens"]
        output_tokens = result["output_tokens"]

        latency = time.perf_counter() - start_time

        REQUEST_COUNT.labels(status="success").inc()
        REQUEST_LATENCY.observe(latency)

        TOKEN_COUNT.labels(token_type="input").inc(input_tokens)
        TOKEN_COUNT.labels(token_type="output").inc(output_tokens)

        return {
            "answer": answer,
            "model": "mock-model",
            "latency_ms": round(latency * 1000, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }

    except Exception:
        REQUEST_COUNT.labels(status="error").inc()
        ERROR_COUNT.inc()

        raise HTTPException(
            status_code=500,
            detail="Request processing failed"
        )


# Expose Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)



