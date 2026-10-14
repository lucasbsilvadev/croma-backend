import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_user():
    """
    Payload válido de cadastro. Senha atende à política forte.
    CPF: 11144477735 (válido, dígitos verificadores conferem).
    """
    return {
        "nome": "Fulano Teste",
        "email": "fulano@example.com",
        "password": "SenhaSegura123!",
        "cpf_cnpj": "11144477735",
        "terms_version": "2026-10-13",
    }


@pytest.fixture(autouse=True)
def clear_overrides():
    """Limpa dependency_overrides entre testes — evita vazamento."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_logging():
    """
    Força propagação dos loggers da app durante os testes.
    Sem isso, o handler do caplog do pytest pode ser ignorado
    quando algum módulo configura logging no import.
    """
    root = logging.getLogger()
    app_logger = logging.getLogger("app")

    old_root_level = root.level
    old_app_level = app_logger.level
    old_app_propagate = app_logger.propagate

    root.setLevel(logging.DEBUG)
    app_logger.setLevel(logging.DEBUG)
    app_logger.propagate = True

    yield

    root.setLevel(old_root_level)
    app_logger.setLevel(old_app_level)
    app_logger.propagate = old_app_propagate


@pytest.fixture
def mock_profile_repo():
    """
    ProfileRepository fake com comportamento mínimo consistente.
    Use quando precisar de controle fino sobre get_by_user_id/create/ensure_profile.
    """
    repo = MagicMock()
    repo.get_by_user_id.return_value = None
    return repo