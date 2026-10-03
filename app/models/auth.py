from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload de cadastro."""

    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    # Limite de 72 para evitar truncamento silencioso em algoritmos
    # de hash do Supabase Auth. Ver docs/auth.md.
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    """Payload de login."""

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
