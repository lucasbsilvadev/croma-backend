"""Testes unitários do ShippingService. Mocka repositório."""

from unittest.mock import MagicMock

import pytest

from app.services.shipping_service import ShippingService
from app.utils.exceptions import ValidationError


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def service(repo):
    return ShippingService(shipping_repo=repo)


class TestQuote:
    def test_returns_zone_for_cep_in_range(self, service, repo):
        repo.find_zone_by_cep.return_value = {
            "nome": "DF",
            "cep_prefixo_min": "70000000",
            "cep_prefixo_max": "72799999",
            "valor_cents": 1500,
            "prazo_dias": 2,
        }

        result = service.quote("73062702")

        assert result["zona"] == "DF"
        assert result["valor"] == "15.00"
        assert result["prazo_dias"] == 2

    def test_normalizes_cep_with_dash(self, service, repo):
        repo.find_zone_by_cep.return_value = {
            "nome": "DF",
            "valor_cents": 1500,
            "prazo_dias": 2,
        }

        service.quote("73062-702")

        # Repo recebeu só dígitos
        repo.find_zone_by_cep.assert_called_once_with("73062702")

    def test_raises_when_no_zone_covers_cep(self, service, repo):
        repo.find_zone_by_cep.return_value = None

        with pytest.raises(ValidationError, match="indisponível"):
            service.quote("00000000")

    def test_raises_on_invalid_cep_length(self, service, repo):
        with pytest.raises(ValidationError, match="CEP inválido"):
            service.quote("123")