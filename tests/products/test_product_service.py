"""Testes unitários do ProductService. Mocka repositório."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.product_service import ProductService
from app.utils.exceptions import ConflictError, NotFoundError


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def service(repo):
    return ProductService(product_repo=repo)


class TestCreateProduct:
    def test_creates_product_with_valid_data(self, service, repo):
        repo.exists_slug.return_value = False
        repo.create.return_value = {
            "id": "p1", "nome": "NØ CAP", "slug": "no-cap",
            "descricao": None, "preco": Decimal("112.00"),
            "estoque": 5, "ativo": True, "created_at": "2026-10-04T00:00:00Z",
        }
        repo.list_images.return_value = []

        result = service.create_product({
            "nome": "NØ CAP", "slug": "no-cap", "preco": Decimal("112.00"),
            "estoque": 5, "descricao": None,
        })

        assert result["slug"] == "no-cap"
        repo.create.assert_called_once()

    def test_raises_conflict_on_duplicate_slug(self, service, repo):
        repo.exists_slug.return_value = True

        with pytest.raises(ConflictError, match="Slug já existe"):
            service.create_product({
                "nome": "X", "slug": "no-cap", "preco": Decimal("10.00"),
                "estoque": 0, "descricao": None,
            })


class TestGetActiveBySlug:
    def test_returns_active_product(self, service, repo):
        repo.get_by_slug.return_value = {
            "id": "p1", "nome": "NØ CAP", "slug": "no-cap",
            "descricao": None, "preco": Decimal("112.00"),
            "estoque": 5, "ativo": True, "created_at": "2026-10-04T00:00:00Z",
        }
        repo.list_images.return_value = []

        result = service.get_active_by_slug("no-cap")
        assert result["slug"] == "no-cap"

    def test_raises_not_found_when_inactive(self, service, repo):
        repo.get_by_slug.return_value = {
            "id": "p1", "slug": "no-cap", "ativo": False,
        }
        with pytest.raises(NotFoundError):
            service.get_active_by_slug("no-cap")

    def test_raises_not_found_when_missing(self, service, repo):
        repo.get_by_slug.return_value = None
        with pytest.raises(NotFoundError):
            service.get_active_by_slug("nao-existe")


class TestUpdateProduct:
    def test_partial_update(self, service, repo):
        repo.get_by_id.return_value = {
            "id": "p1", "nome": "NØ CAP", "slug": "no-cap",
            "ativo": True, "preco": Decimal("112.00"),
            "estoque": 5, "descricao": None, "created_at": "2026-10-04T00:00:00Z",
        }
        repo.update.return_value = {
            "id": "p1", "nome": "NØ CAP NOVO", "slug": "no-cap",
            "ativo": True, "preco": Decimal("112.00"),
            "estoque": 5, "descricao": None, "created_at": "2026-10-04T00:00:00Z",
        }
        repo.list_images.return_value = []

        result = service.update_product("p1", {"nome": "NØ CAP NOVO"})

        assert result["nome"] == "NØ CAP NOVO"
        call_args = repo.update.call_args
        assert call_args[0][1] == {"nome": "NØ CAP NOVO"}

    def test_raises_not_found(self, service, repo):
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.update_product("p-x", {"nome": "X"})


class TestSoftDelete:
    def test_soft_delete_sets_ativo_false(self, service, repo):
        repo.get_by_id.return_value = {"id": "p1", "ativo": True, "slug": "x"}
        repo.soft_delete.return_value = {
            "id": "p1", "nome": "X", "slug": "x", "ativo": False,
            "preco": Decimal("10.00"), "estoque": 0, "descricao": None,
            "created_at": "2026-10-04T00:00:00Z",
        }
        repo.list_images.return_value = []

        result = service.soft_delete("p1")
        assert result["ativo"] is False

    def test_raises_not_found(self, service, repo):
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.soft_delete("p-x")