
from locust import HttpUser, task, between


class LLMUser(HttpUser):

    # Wait between 1 and 3 seconds before executing the next task
    wait_time = between(1, 3)

    @task
    def ask_question(self):

        self.client.post(
            "/ask",
            json={
                "question": "What is LLM observability?"
            },
            name="/ask"
        )
