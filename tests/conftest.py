import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_user():
    return {
        "nome": "Fulano Teste",
        "email": "fulano@example.com",
        "password": "senhaSegura123",
    }