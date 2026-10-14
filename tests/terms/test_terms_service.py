"""Testes unitários do TermsService. Mocka repositório."""
from unittest.mock import MagicMock

import pytest

from app.services.terms_service import TermsService
from app.utils.exceptions import NotFoundError, ValidationError


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def service(repo):
    return TermsService(terms_repo=repo)


def _version(version="2026-10-13", ativo=True):
    return {
        "id": "tv-1",
        "version": version,
        "effective_at": "2026-10-13T00:00:00Z",
        "document_hash": "sha256-abc",
        "url": "https://cromadrip.com.br/termos",
        "ativo": ativo,
    }


class TestGetCurrent:
    def test_returns_current_version(self, service, repo):
        repo.get_current_version.return_value = _version()
        result = service.get_current()
        assert result["version"] == "2026-10-13"
        assert result["url"] == "https://cromadrip.com.br/termos"

    def test_raises_404_when_none(self, service, repo):
        repo.get_current_version.return_value = None
        with pytest.raises(NotFoundError, match="vigente"):
            service.get_current()


class TestValidateVersion:
    def test_returns_row_when_active(self, service, repo):
        row = _version()
        repo.get_active_version.return_value = row
        result = service.validate_version("2026-10-13")
        assert result == row
        repo.get_active_version.assert_called_once_with("2026-10-13")

    def test_raises_when_unknown(self, service, repo):
        repo.get_active_version.return_value = None
        with pytest.raises(ValidationError, match="inválida"):
            service.validate_version("banana")

    def test_raises_when_inactive(self, service, repo):
        # get_active_version já filtra ativo=True, então inativa retorna None
        repo.get_active_version.return_value = None
        with pytest.raises(ValidationError):
            service.validate_version("v0-template")