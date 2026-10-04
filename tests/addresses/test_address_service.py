"""Testes unitários do AddressService. Mocka repositório."""

from unittest.mock import MagicMock

import pytest

from app.services.address_service import AddressService
from app.utils.exceptions import NotFoundError


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def service(repo):
    return AddressService(address_repo=repo)


def _addr(id="a1", user_id="u1", principal=False):
    return {
        "id": id, "user_id": user_id,
        "nome_destinatario": "Fulano", "cep": "70000000",
        "logradouro": "Rua X", "numero": "10", "complemento": None,
        "bairro": "Centro", "cidade": "Brasília", "estado": "DF",
        "principal": principal, "created_at": "2026-10-04T00:00:00Z",
    }


class TestCreate:
    def test_first_address_becomes_principal(self, service, repo):
        """Primeiro endereço do user vira principal automaticamente."""
        repo.count_by_user.return_value = 0
        repo.create.return_value = _addr(principal=True)

        result = service.create("u1", {
            "nome_destinatario": "Fulano", "cep": "70000000",
            "logradouro": "Rua X", "bairro": "Centro",
            "cidade": "Brasília", "estado": "DF", "principal": False,
        })

        assert result["principal"] is True
        call_data = repo.create.call_args[0][1]
        assert call_data["principal"] is True

    def test_second_address_with_principal_desmarca_anterior(self, service, repo):
        """Segundo endereço marcado como principal desmarca o primeiro."""
        repo.count_by_user.return_value = 1
        repo.create.return_value = _addr(id="a2", principal=True)

        service.create("u1", {
            "nome_destinatario": "Fulano", "cep": "70000000",
            "logradouro": "Rua Y", "bairro": "Centro",
            "cidade": "Brasília", "estado": "DF", "principal": True,
        })

        repo.clear_principal.assert_called_once_with("u1")

    def test_second_address_without_principal_does_not_clear(self, service, repo):
        """Segundo endereço NÃO principal não mexe no principal atual."""
        repo.count_by_user.return_value = 1
        repo.create.return_value = _addr(id="a2", principal=False)

        service.create("u1", {
            "nome_destinatario": "Fulano", "cep": "70000000",
            "logradouro": "Rua Y", "bairro": "Centro",
            "cidade": "Brasília", "estado": "DF", "principal": False,
        })

        repo.clear_principal.assert_not_called()


class TestGetOne:
    def test_returns_address_if_owned(self, service, repo):
        repo.get_by_id_and_user.return_value = _addr()
        result = service.get_one("u1", "a1")
        assert result["id"] == "a1"

    def test_raises_404_if_not_owned(self, service, repo):
        """Endereço de outro user → 404 (não vaza existência)."""
        repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            service.get_one("u1", "a-do-outro")


class TestUpdate:
    def test_partial_update(self, service, repo):
        repo.get_by_id_and_user.return_value = _addr()
        updated = _addr()
        updated["cidade"] = "Goiânia"
        repo.update.return_value = updated

        result = service.update("u1", "a1", {"cidade": "Goiânia"})

        assert result["cidade"] == "Goiânia"
        call_data = repo.update.call_args[0][1]
        assert call_data == {"cidade": "Goiânia"}

    def test_marking_as_principal_clears_others(self, service, repo):
        repo.get_by_id_and_user.return_value = _addr(principal=False)
        repo.update.return_value = _addr(principal=True)

        service.update("u1", "a1", {"principal": True})

        repo.clear_principal.assert_called_once_with("u1")

    def test_raises_404_if_not_owned(self, service, repo):
        repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            service.update("u1", "a-do-outro", {"cidade": "X"})


class TestDelete:
    def test_delete_principal_promotes_oldest(self, service, repo):
        """Deletar principal promove o mais antigo restante."""
        repo.get_by_id_and_user.return_value = _addr(principal=True)
        repo.get_oldest_by_user.return_value = _addr(id="a2")

        service.delete("u1", "a1")

        repo.delete.assert_called_once_with("a1")
        repo.update.assert_called_once_with("a2", {"principal": True})

    def test_delete_non_principal_does_not_promote(self, service, repo):
        repo.get_by_id_and_user.return_value = _addr(principal=False)

        service.delete("u1", "a1")

        repo.delete.assert_called_once_with("a1")
        repo.get_oldest_by_user.assert_not_called()

    def test_delete_last_address_does_not_promote(self, service, repo):
        """Se era o último, não tenta promover."""
        repo.get_by_id_and_user.return_value = _addr(principal=True)
        repo.get_oldest_by_user.return_value = None

        service.delete("u1", "a1")

        repo.delete.assert_called_once_with("a1")
        repo.update.assert_not_called()

    def test_raises_404_if_not_owned(self, service, repo):
        repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            service.delete("u1", "a-do-outro")