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