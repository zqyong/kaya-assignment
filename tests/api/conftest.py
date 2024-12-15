import pytest
from httpx import Client

HOST_URL = "http://localhost:8000"


@pytest.fixture
def app_client():
    client = Client(base_url=HOST_URL)
    yield client
