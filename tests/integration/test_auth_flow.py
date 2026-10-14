"""
Teste de integração do fluxo completo de auth contra o Supabase real.

Marca `integration` — NÃO roda por padrão. Roda só quando:
    pytest -m integration

Objetivo: pegar bugs que unitários com mock não pegam
(ex: SDK mudou URL, shape da resposta mudou, rate limit).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration

_TERMS_VERSION = "2026-10-13"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def unique_email():
    """Gera email único pra não colidir com testes anteriores."""
    return f"croma-test+{uuid.uuid4().hex[:8]}@gmail.com"


def test_full_auth_flow(client, unique_email):
    """
    Fluxo completo:
    1. Register com email novo → 201 com tokens
    2. Login com mesmas credenciais → 200 com tokens
    3. GET /me com access_token → 200 com profile
    """
    password = "SenhaSegura123!"

    # 1. Register
    register_res = client.post(
        "/auth/register",
        json={
            "nome": "Teste Integracao",
            "email": unique_email,
            "password": password,
            "cpf_cnpj": "11144477735",
            "terms_version": _TERMS_VERSION,
        },
    )
    assert register_res.status_code == 201, register_res.text
    register_body = register_res.json()
    assert register_body["user_id"]
    assert register_body["access_token"]
    assert register_body["refresh_token"]

    # 2. Login
    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    login_body = login_res.json()
    access_token = login_body["access_token"]
    assert access_token

    # 3. GET /me com token real
    me_res = client.get("/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_res.status_code == 200, me_res.text
    me_body = me_res.json()
    assert me_body["user_id"] == register_body["user_id"]
    assert me_body["email"] == unique_email
    assert me_body["nome"] == "Teste Integracao"
    # CPF volta normalizado (só dígitos), sem máscara.
    assert me_body["cpf_cnpj"] == "11144477735"
    assert me_body["tipo_pessoa"] == "fisica"


def test_register_with_formatted_cpf_is_normalized(client, unique_email):
    """
    Cadastro com CPF pontuado deve ser aceito e normalizado (só dígitos).
    Esse é o coração do 'aceitar com ou sem pontuação'.
    """
    res = client.post(
        "/auth/register",
        json={
            "nome": "Teste Pontuado",
            "email": unique_email,
            "password": "SenhaSegura123!",
            "cpf_cnpj": "111.444.777-35",
            "terms_version": _TERMS_VERSION,
        },
    )
    assert res.status_code == 201, res.text

    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": "SenhaSegura123!"},
    )
    assert login_res.status_code == 200, login_res.text
    access_token = login_res.json()["access_token"]

    me_res = client.get("/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_res.status_code == 200, me_res.text
    assert me_res.json()["cpf_cnpj"] == "11144477735"


def test_register_without_terms_version_returns_422(client, unique_email):
    """Sem terms_version → 422 (obrigatório desde a iteração de Termos)."""
    res = client.post(
        "/auth/register",
        json={
            "nome": "Sem Termo",
            "email": unique_email,
            "password": "SenhaSegura123!",
            "cpf_cnpj": "11144477735",
        },
    )
    assert res.status_code == 422, res.text


def test_register_with_invalid_cpf_returns_422(client, unique_email):
    """CPF com dígito verificador errado → 422 (rejeitado no boundary)."""
    res = client.post(
        "/auth/register",
        json={
            "nome": "CPF Ruim",
            "email": unique_email,
            "password": "SenhaSegura123!",
            "cpf_cnpj": "111.444.777-36",
            "terms_version": _TERMS_VERSION,
        },
    )
    assert res.status_code == 422, res.text


def test_me_with_invalid_token_returns_401(client):
    """Token inválido → 401 (validação real no Supabase)."""
    res = client.get("/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert res.status_code == 401