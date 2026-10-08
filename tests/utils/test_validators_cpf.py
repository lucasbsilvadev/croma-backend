# tests/utils/test_validators_cpf.py
from app.utils.validators import (
    is_valid_cpf, is_valid_cnpj, is_valid_cpf_cnpj, derive_tipo_pessoa,
)

def test_cpf_valido():
    assert is_valid_cpf("111.444.777-35")
    assert is_valid_cpf("11144477735")

def test_cpf_invalido_dv():
    assert not is_valid_cpf("111.444.777-36")

def test_cpf_todos_iguais():
    assert not is_valid_cpf("11111111111")

def test_cnpj_valido():
    assert is_valid_cnpj("11.222.333/0001-81")

def test_derive_tipo():
    assert derive_tipo_pessoa("11144477735") == "fisica"
    assert derive_tipo_pessoa("11222333000181") == "juridica"