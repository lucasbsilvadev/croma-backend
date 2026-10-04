from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ProductCreateRequest(BaseModel):
    """Payload de criação de produto (admin)."""

    nome: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=200)
    descricao: str | None = None
    preco: Decimal = Field(gt=0)
    estoque: int = Field(ge=0, default=0)

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        """Slug só aceita a-z, 0-9 e hífen. Evita URL quebrada."""
        import re
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", v):
            raise ValueError(
                "Slug deve conter apenas letras minúsculas, números e hífens"
            )
        return v


class ProductUpdateRequest(BaseModel):
    """Payload de atualização parcial. Todos os campos opcionais."""

    nome: str | None = Field(default=None, min_length=2, max_length=200)
    descricao: str | None = None
    preco: Decimal | None = Field(default=None, gt=0)
    estoque: int | None = Field(default=None, ge=0)
    ativo: bool | None = None


class ProductImageResponse(BaseModel):
    """Imagem de um produto."""

    id: str
    url: str
    position: int


class ProductResponse(BaseModel):
    """Produto exposto pela API."""

    id: str
    nome: str
    slug: str
    descricao: str | None
    preco: str           # Decimal serializado como string pra não perder precisão
    estoque: int
    ativo: bool
    imagens: list[ProductImageResponse] = []
    created_at: datetime

    @field_validator("preco", mode="before")
    @classmethod
    def decimal_to_str(cls, v):
        """Converte Decimal/float/str pra string com 2 casas."""
        if isinstance(v, Decimal):
            return f"{v:.2f}"
        if isinstance(v, (int, float)):
            return f"{Decimal(str(v)):.2f}"
        if isinstance(v, str):
            return f"{Decimal(v):.2f}"
        return v


class ProductImageCreateRequest(BaseModel):
    """Payload de adicionar imagem."""

    url: str = Field(min_length=1)
    position: int = Field(ge=0, default=0)