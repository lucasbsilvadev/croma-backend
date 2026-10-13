from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings


def _parse_origins(raw: str) -> list[str]:
    """Parseia lista comma-separated; ignora vazios e espaços."""
    return [o.strip() for o in raw.split(",") if o.strip()]


def setup_cors(app: FastAPI) -> None:
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

    extra = _parse_origins(settings.extra_cors_origins)
    origins += extra

    seen: set[str] = set()
    unique_origins: list[str] = []
    for origin in origins:
        if origin not in seen:
            seen.add(origin)
            unique_origins.append(origin)

    # DIAGNÓSTICO — remover quando CORS estiver 100%.
    import logging
    logging.getLogger(__name__).info(
        f"CORS_SETUP origins={unique_origins!r} "
        f"extra_raw={settings.extra_cors_origins!r} "
        f"env={settings.env!r}"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=unique_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )