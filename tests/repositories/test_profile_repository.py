"""
Testes unitários do ProfileRepository.
Mocka supabase_admin.table(...) — não bate no Supabase real.

Foco: idempotência real e tratamento de race conditions do ensure_profile.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.repositories.profile_repository import ProfileRepository
from app.utils.exceptions import ConflictError


def _mock_table_chain(select_data: list, insert_data: list | None = None):
    """
    Cria um mock da chain supabase_admin.table(...).select(...).eq(...).execute()
    que devolve `select_data` no execute.
    """
    mock_execute = MagicMock()
    mock_execute.execute.return_value = MagicMock(data=select_data)

    mock_eq = MagicMock()
    mock_eq.eq.return_value = mock_execute

    mock_select = MagicMock()
    mock_select.select.return_value = mock_eq

    if insert_data is not None:
        mock_insert_execute = MagicMock()
        mock_insert_execute.execute.return_value = MagicMock(data=insert_data)

        mock_insert = MagicMock()
        mock_insert.insert.return_value = mock_insert_execute
        mock_select.insert = mock_insert.insert

    return mock_select


# ============================================================
# get_by_user_id
# ============================================================


class TestGetByUserId:
    def test_returns_none_when_no_rows(self):
        with patch("app.repositories.profile_repository.supabase_admin") as mock_sb:
            mock_sb.table.return_value = _mock_table_chain(select_data=[])
            repo = ProfileRepository()
            assert repo.get_by_user_id("u1") is None

    def test_returns_first_row_when_exists(self):
        row = {"user_id": "u1", "nome": "Fulano", "role": "user"}
        with patch("app.repositories.profile_repository.supabase_admin") as mock_sb:
            mock_sb.table.return_value = _mock_table_chain(select_data=[row])
            repo = ProfileRepository()
            assert repo.get_by_user_id("u1") == row


# ============================================================
# create
# ============================================================


class TestCreate:
    def test_raises_conflict_when_already_exists(self):
        existing = {"user_id": "u1", "nome": "Fulano", "role": "user"}
        with patch("app.repositories.profile_repository.supabase_admin") as mock_sb:
            mock_sb.table.return_value = _mock_table_chain(select_data=[existing])
            repo = ProfileRepository()

            with pytest.raises(ConflictError):
                repo.create(user_id="u1", nome="Fulano")

    def test_inserts_and_returns_new_row(self):
        new_row = {"user_id": "u1", "nome": "Fulano", "role": "user"}

        with patch("app.repositories.profile_repository.supabase_admin") as mock_sb:
            # 1ª chamada: get_by_user_id dentro do create (retorna vazio)
            # 2ª chamada: insert.execute() retorna a linha criada
            mock_table = MagicMock()

            # get_by_user_id retorna vazio
            mock_get_execute = MagicMock()
            mock_get_execute.execute.return_value = MagicMock(data=[])
            mock_get_eq = MagicMock()
            mock_get_eq.eq.return_value = mock_get_execute
            mock_table.select.return_value = mock_get_eq

            # insert retorna a linha nova
            mock_insert_execute = MagicMock()
            mock_insert_execute.execute.return_value = MagicMock(data=[new_row])
            mock_table.insert.return_value = mock_insert_execute

            mock_sb.table.return_value = mock_table
            repo = ProfileRepository()

            result = repo.create(user_id="u1", nome="Fulano")

        assert result == new_row


# ============================================================
# ensure_profile — o coração
# ============================================================


class TestEnsureProfile:
    def test_returns_existing_without_calling_create(self):
        """
        Se o profile já existe, ensure_profile NÃO deve tentar criar.
        Isso é o que evita o ConflictError em condição normal.
        """
        existing = {"user_id": "u1", "nome": "Fulano", "role": "user"}

        with patch("app.repositories.profile_repository.supabase_admin") as mock_sb:
            mock_sb.table.return_value = _mock_table_chain(select_data=[existing])
            repo = ProfileRepository()
            repo.create = MagicMock()

            result = repo.ensure_profile(user_id="u1", nome="Fulano")

        assert result == existing
        repo.create.assert_not_called()

    def test_calls_create_when_missing(self):
        """Se não existe, chama create."""
        new_row = {"user_id": "u1", "nome": "Fulano", "role": "user"}

        with patch("app.repositories.profile_repository.supabase_admin") as mock_sb:
            # get retorna vazio
            mock_table = MagicMock()
            mock_get_execute = MagicMock()
            mock_get_execute.execute.return_value = MagicMock(data=[])
            mock_get_eq = MagicMock()
            mock_get_eq.eq.return_value = mock_get_execute
            mock_table.select.return_value = mock_get_eq

            # insert retorna nova linha
            mock_insert_execute = MagicMock()
            mock_insert_execute.execute.return_value = MagicMock(data=[new_row])
            mock_table.insert.return_value = mock_insert_execute

            mock_sb.table.return_value = mock_table
            repo = ProfileRepository()

            result = repo.ensure_profile(user_id="u1", nome="Fulano")

        assert result == new_row

    def test_handles_conflict_error_from_race_and_returns_existing(self):
        """
        Race real: entre nosso `get` e o `insert`, outro request criou o
        profile. `create` levanta ConflictError. `ensure_profile` deve
        refazer o `get` e devolver o profile que o outro criou.
        """
        existing = {"user_id": "u1", "nome": "Fulano", "role": "user"}

        repo = ProfileRepository()
        # Primeiro get: vazio (race começou)
        # create: levanta ConflictError (outro já criou)
        # Segundo get: encontra
        repo.get_by_user_id = MagicMock(side_effect=[None, existing])
        repo.create = MagicMock(side_effect=ConflictError())

        result = repo.ensure_profile(user_id="u1", nome="Fulano")

        assert result == existing

    def test_handles_api_error_23505_unique_violation(self):
        """
        Supabase devolve APIError 23505 (unique violation) quando
        dois inserts simultâneos batem na UNIQUE constraint.
        ensure_profile deve refazer o get.
        """
        existing = {"user_id": "u1", "nome": "Fulano", "role": "user"}

        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        repo = ProfileRepository()
        repo.get_by_user_id = MagicMock(side_effect=[None, existing])
        repo.create = MagicMock(side_effect=FakeAPIError("23505"))

        result = repo.ensure_profile(user_id="u1", nome="Fulano")

        assert result == existing

    def test_handles_api_error_23503_fk_violation(self):
        """
        FK violation (23503): user ainda não commitou em auth.users.
        ensure_profile tenta de novo o get — se o user já commitou, acha.
        """
        existing = {"user_id": "u1", "nome": "Fulano", "role": "user"}

        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        repo = ProfileRepository()
        repo.get_by_user_id = MagicMock(side_effect=[None, existing])
        repo.create = MagicMock(side_effect=FakeAPIError("23503"))

        result = repo.ensure_profile(user_id="u1", nome="Fulano")

        assert result == existing

    def test_propagates_unknown_api_error(self):
        """
        Erro que NÃO é 23505/23503 deve propagar.
        Não esconder bug real do banco atrás de um 'return None'.
        """
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        repo = ProfileRepository()
        repo.get_by_user_id = MagicMock(return_value=None)
        repo.create = MagicMock(side_effect=FakeAPIError("42P01"))

        with pytest.raises(FakeAPIError):
            repo.ensure_profile(user_id="u1", nome="Fulano")

    def test_propagates_when_retry_get_still_returns_none(self):
        """
        Se mesmo após o erro não conseguimos achar o profile,
        propaga o erro original. Não inventa sucesso.
        """
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        repo = ProfileRepository()
        repo.get_by_user_id = MagicMock(return_value=None)  # sempre vazio
        repo.create = MagicMock(side_effect=FakeAPIError("23503"))

        with pytest.raises(FakeAPIError):
            repo.ensure_profile(user_id="u1", nome="Fulano")

    def test_idempotent_when_called_multiple_times(self):
        """
        Chamar ensure_profile N vezes seguidas cria no máximo 1 profile.
        Depois da primeira, todas as chamadas retornam o existente.
        """
        existing = {"user_id": "u1", "nome": "Fulano", "role": "user"}

        repo = ProfileRepository()
        # Primeira chamada: get vazio → create → retorna linha
        # Chamadas seguintes: get acha
        repo.get_by_user_id = MagicMock(
            side_effect=[None, existing, existing, existing, existing]
        )
        repo.create = MagicMock(return_value=existing)

        results = [repo.ensure_profile(user_id="u1", nome="Fulano") for _ in range(5)]

        assert all(r == existing for r in results)
        # create chamado APENAS 1 vez, mesmo com 5 chamadas a ensure
        assert repo.create.call_count == 1