import random
import time
from pathlib import Path
from locust import HttpUser, task, between


SAMPLE_QUERIES = [
    "What is attention in transformers?",
    "Explain self-attention",
    "How do transformers work?",
    "What is multi-head attention?",
    "What is the transformer architecture?",
]
TEST_DOCS = [Path(__file__).parent.parent / "fixtures" / "test_doc.pdf"]
BASE_URL = "http://localhost:8000"


def get_auth_token(client):
    response = client.post(
        f"{BASE_URL}/auth/token",
        data={"username": "admin-client", "password": "admin-secret"},
    )
    return response.json()["access_token"]


class QueryUser(HttpUser):
    weight = 7
    wait_time = between(1, 3)

    def on_start(self):
        self.token = get_auth_token(self.client)

    @task
    def query_pipeline(self):
        self.client.post(
            f"{BASE_URL}/query",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "query": random.choice(SAMPLE_QUERIES),
                "stream": False,
            },
        )


class IngestUser(HttpUser):
    weight = 2
    wait_time = between(3, 5)

    def on_start(self):
        self.token = get_auth_token(self.client)

    @task
    def ingest_document(self):
        doc_path = random.choice(TEST_DOCS)
        with open(doc_path, "rb") as f:
            self.client.post(
                f"{BASE_URL}/ingest",
                headers={"Authorization": f"Bearer {self.token}"},
                files={"file": (doc_path.name, f, "application/pdf")},
            )


class AdminUser(HttpUser):
    weight = 1
    wait_time = between(5, 10)

    def on_start(self):
        self.token = get_auth_token(self.client)

    @task
    def check_evaluations(self):
        self.client.get(
            f"{BASE_URL}/evaluations",
            headers={"Authorization": f"Bearer {self.token}"},
        )
