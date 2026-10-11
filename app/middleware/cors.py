from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings


def _parse_origins(raw: str) -> list[str]:
    """Parseia lista comma-separated; ignora vazios e espaços."""
    return [o.strip() for o in raw.split(",") if o.strip()]


def setup_cors(app: FastAPI) -> None:
    """
    CORS restritivo.

    Origens:
      - Domínios oficiais: sempre liberados.
      - localhost: só em dev (ENV=dev).
      - EXTRA_CORS_ORIGINS: domínios temporários de teste (comma-separated),
        pra permitir validar em prod de teste antes do domínio oficial entrar.
    """
    origins: list[str] = [
        "https://cromadrip.com.br",
        "https://www.cromadrip.com.br",
    ]

    if settings.is_dev:
        origins += [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    origins += _parse_origins(settings.extra_cors_origins)

    # Dedup preservando ordem
    seen: set[str] = set()
    unique_origins: list[str] = []
    for origin in origins:
        if origin not in seen:
            seen.add(origin)
            unique_origins.append(origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=unique_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )