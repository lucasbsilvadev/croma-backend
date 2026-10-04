from pydantic import BaseModel


class Profile(BaseModel):
    """Representação do perfil no banco de dados."""
    user_id: str
    nome: str
    role: str = "user"  # 'user' ou 'admin'


class MeResponse(BaseModel):
    """Resposta do GET /me."""
    user_id: str
    email: str
    nome: str
    role: str
