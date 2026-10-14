"""
Contratos HTTP do módulo de termos.
Referência: LGPD-01.
"""
from datetime import datetime

from pydantic import BaseModel


class TermsCurrentResponse(BaseModel):
    """Resposta de GET /terms/current."""

    version: str
    effective_at: datetime
    url: str | None = None