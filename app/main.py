from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.middleware.cors import setup_cors
from app.middleware.rate_limit import limiter
from app.routes import auth_routes, profile_routes

app = FastAPI(
    title="Croma Drip API",
    version="0.1.0",
    description="Backend MVP da Croma Drip",
)

# CORS precisa ser configurado ANTES dos routers
setup_cors(app)

# Rate limit
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# routers

app.include_router(auth_routes.router)
app.include_router(profile_routes.router)

@app.get("/health", tags=["infra"])
async def health():
    """Healthcheck. Usado por hosting/monitoramento."""
    return {"status": "ok"}



