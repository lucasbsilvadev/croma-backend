from datetime import datetime

from pydantic import BaseModel, Field


class AddressCreateRequest(BaseModel):
    """Payload de criação de endereço/ponto de entrega (cliente)."""

    nome_destinatario: str = Field(min_length=2, max_length=200)
    cep: str = Field(min_length=8, max_length=9)
    logradouro: str = Field(min_length=2, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=200)
    bairro: str = Field(min_length=2, max_length=100)
    cidade: str = Field(min_length=2, max_length=100)
    estado: str = Field(min_length=2, max_length=2)
    principal: bool = False


class AddressUpdateRequest(BaseModel):
    """Atualização parcial. Todos os campos opcionais."""

    nome_destinatario: str | None = Field(default=None, min_length=2, max_length=200)
    cep: str | None = Field(default=None, min_length=8, max_length=9)
    logradouro: str | None = Field(default=None, min_length=2, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=200)
    bairro: str | None = Field(default=None, min_length=2, max_length=100)
    cidade: str | None = Field(default=None, min_length=2, max_length=100)
    estado: str | None = Field(default=None, min_length=2, max_length=2)
    principal: bool | None = None


class AddressResponse(BaseModel):
    """Endereço/ponto de entrega exposto pela API."""

    id: str
    nome_destinatario: str
    cep: str
    logradouro: str
    numero: str | None
    complemento: str | None
    bairro: str
    cidade: str
    estado: str
    principal: bool
    created_at: datetime