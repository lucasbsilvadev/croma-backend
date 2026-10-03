from pydantic import BaseModel


class MeResponse(BaseModel):
    """Resposta do GET /me."""

    user_id: str
    email: str
    nome: str
