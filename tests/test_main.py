
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_home():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == (
        "LLM Observability Platform is running!"
    )


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ask_success():
    response = client.post(
        "/ask",
        json={"question": "What is Docker?"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"]
    assert data["model"] == "mock-model"
    assert data["latency_ms"] >= 0
    assert data["input_tokens"] > 0
    assert data["output_tokens"] > 0


def test_ask_empty_question():
    response = client.post(
        "/ask",
        json={"question": ""}
    )

    assert response.status_code == 422


def test_ask_missing_question():
    response = client.post(
        "/ask",
        json={}
    )

    assert response.status_code == 422


def test_metrics_endpoint():
    client.post(
        "/ask",
        json={"question": "Test metrics"}
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "llm_requests_total" in response.text
