"""
Validadores reutilizáveis. Vivem aqui para não poluir models/services.
"""
import re

# Política de senha forte (aplicada só no cadastro/recuperação — NÃO no login)
# - 8 a 72 caracteres (72 = limite do hash bcrypt do Supabase)
# - pelo menos 1 minúscula, 1 maiúscula, 1 dígito, 1 caractere especial
_SPECIAL = r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\/;'`~]"
_PASSWORD_REGEX = re.compile(
    rf"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*{_SPECIAL}).{{8,72}}$"
)

PASSWORD_RULES_MESSAGE = (
    "A senha deve ter entre 8 e 72 caracteres, incluindo pelo menos "
    "uma letra maiúscula, uma minúscula, um número e um caractere especial."
)


def is_strong_password(value: str) -> bool:
    """True se a senha atende à política forte."""
    return bool(_PASSWORD_REGEX.match(value))

# ============================================================
# CPF / CNPJ
# ============================================================

CPF_LENGTH = 11
CNPJ_LENGTH = 14


def normalize_cpf_cnpj(value: str) -> str:
    """Remove máscara. Só dígitos."""
    return "".join(c for c in value if c.isdigit())


def _all_same_digits(value: str) -> bool:
    return len(set(value)) == 1


def _cpf_check_digits(cpf: str) -> str:
    """Calcula os 2 dígitos verificadores do CPF."""
    digits = [int(d) for d in cpf[:9]]
    for _ in range(2):
        weight = len(digits) + 1
        total = sum(d * (weight - i) for i, d in enumerate(digits))
        dv = 11 - (total % 11)
        digits.append(0 if dv >= 10 else dv)
    return "".join(str(d) for d in digits[9:])


def _cnpj_check_digits(cnpj: str) -> str:
    """Calcula os 2 dígitos verificadores do CNPJ."""
    digits = [int(d) for d in cnpj[:12]]
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    total = sum(d * w for d, w in zip(digits, weights1))
    dv1 = 11 - (total % 11)
    dv1 = 0 if dv1 >= 10 else dv1
    digits.append(dv1)

    total = sum(d * w for d, w in zip(digits, weights2))
    dv2 = 11 - (total % 11)
    dv2 = 0 if dv2 >= 10 else dv2
    digits.append(dv2)

    return f"{dv1}{dv2}"


def is_valid_cpf(value: str) -> bool:
    """Valida CPF: 11 dígitos + dígitos verificadores."""
    cpf = normalize_cpf_cnpj(value)
    if len(cpf) != CPF_LENGTH:
        return False
    if _all_same_digits(cpf):
        return False
    return cpf[9:] == _cpf_check_digits(cpf)


def is_valid_cnpj(value: str) -> bool:
    """Valida CNPJ: 14 dígitos + dígitos verificadores."""
    cnpj = normalize_cpf_cnpj(value)
    if len(cnpj) != CNPJ_LENGTH:
        return False
    if _all_same_digits(cnpj):
        return False
    return cnpj[12:] == _cnpj_check_digits(cnpj)


def is_valid_cpf_cnpj(value: str) -> bool:
    """True se é CPF (11) OU CNPJ (14) válido."""
    normalized = normalize_cpf_cnpj(value)
    if len(normalized) == CPF_LENGTH:
        return is_valid_cpf(normalized)
    if len(normalized) == CNPJ_LENGTH:
        return is_valid_cnpj(normalized)
    return False


def derive_tipo_pessoa(value: str) -> str:
    """
    Deriva 'fisica' ou 'juridica' a partir da quantidade de dígitos.
    Não confia em declaração do cliente.
    """
    normalized = normalize_cpf_cnpj(value)
    if len(normalized) == CPF_LENGTH:
        return "fisica"
    if len(normalized) == CNPJ_LENGTH:
        return "juridica"
    raise ValueError("CPF/CNPJ deve ter 11 ou 14 dígitos")


CPF_CNPJ_RULES_MESSAGE = "CPF/CNPJ inválido"