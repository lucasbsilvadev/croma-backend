from pydantic import BaseModel, Field


class ShippingQuoteRequest(BaseModel):
    """Payload de consulta de frete."""

    cep: str = Field(min_length=8, max_length=9)


class ShippingQuoteResponse(BaseModel):
    """Resultado da consulta de frete."""

    zona: str
    valor: str           # Decimal serializado como string
    prazo_dias: int