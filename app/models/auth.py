from pydantic import BaseModel, EmailStr, Field, field_validator
from app.utils.validators import (
    CPF_CNPJ_RULES_MESSAGE,
    PASSWORD_RULES_MESSAGE,
    is_strong_password,
    is_valid_cpf_cnpj,
    normalize_cpf_cnpj,
)


class RegisterRequest(BaseModel):
    """Payload de cadastro."""

    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    cpf_cnpj: str = Field(min_length=11, max_length=18)
    terms_version: str = Field(min_length=1, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, v: str) -> str:
        if not is_strong_password(v):
            raise ValueError(PASSWORD_RULES_MESSAGE)
        return v

    @field_validator("cpf_cnpj")
    @classmethod
    def validate_cpf_cnpj(cls, v: str) -> str:
        if not is_valid_cpf_cnpj(v):
            raise ValueError(CPF_CNPJ_RULES_MESSAGE)
        return normalize_cpf_cnpj(v)

    @field_validator("terms_version")
    @classmethod
    def validate_terms_version(cls, v: str) -> str:
        """Aceita só versões com formato conhecido (defesa contra payload estranho)."""
        v = v.strip()
        if not v:
            raise ValueError("terms_version não pode ser vazio")
        return v


class LoginRequest(BaseModel):
    """Payload de login. NÃO valida força — só o cadastro exige."""

    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Payload de recuperação de senha."""

    email: EmailStr


class AuthResponse(BaseModel):
    """Resposta de signup/login bem-sucedido."""

    user_id: str
    access_token: str
    refresh_token: str


class MessageResponse(BaseModel):
    """Resposta genérica de mensagem."""

    message: str
