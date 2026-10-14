from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import (
    CPF_CNPJ_RULES_MESSAGE,
    is_valid_cpf_cnpj,
    normalize_cpf_cnpj,
)


class Profile(BaseModel):
    """Representação do perfil no banco de dados."""
    user_id: str
    nome: str
    role: str = "user"  # 'user' ou 'admin'


class MeResponse(BaseModel):
    """Resposta do GET /me."""
    user_id: str
    email: EmailStr
    nome: str
    role: str
    cpf_cnpj: str | None = None
    tipo_pessoa: str | None = None
    terms_version: str | None = None
    terms_accepted_at: datetime | None = None


class ProfileUpdateRequest(BaseModel):
    """
    Payload de PATCH /me.

    Campos opcionais — só o que vier é atualizado.
    - nome: sempre editável.
    - cpf_cnpj: só se o profile ainda não tiver CPF/CNPJ (regra aplicada
      no service, porque depende do estado atual no banco).
    - email/password: NÃO editáveis por aqui (fluxo separado via Supabase Auth).
    """

    nome: str | None = Field(default=None, min_length=2, max_length=100)
    cpf_cnpj: str | None = Field(default=None, min_length=11, max_length=18)

    @field_validator("cpf_cnpj")
    @classmethod
    def validate_cpf_cnpj(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not is_valid_cpf_cnpj(v):
            raise ValueError(CPF_CNPJ_RULES_MESSAGE)
        return normalize_cpf_cnpj(v)

    @field_validator("nome")
    @classmethod
    def validate_nome(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Nome deve ter pelo menos 2 caracteres")
        return v