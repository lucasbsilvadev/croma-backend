from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.middleware.cors import setup_cors
from app.middleware.rate_limit import limiter
from app.middleware.request_id import RequestIdMiddleware
from app.routes import (
    address_routes,
    admin_order_routes,
    admin_product_routes,
    auth_routes,
    order_routes,
    payment_routes,
    product_routes,
    profile_routes,
    shipping_routes,
    terms_routes,
    webhook_routes,
)
from app.utils.logging import setup_logging

# Configura logging estruturado ANTES de qualquer coisa
setup_logging()

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

# middleware de ID da requisição
app.add_middleware(RequestIdMiddleware)

# routers
app.include_router(auth_routes.router)
app.include_router(profile_routes.router)
app.include_router(terms_routes.router)
app.include_router(product_routes.router)
app.include_router(admin_product_routes.router)
app.include_router(address_routes.router)
app.include_router(shipping_routes.router)
app.include_router(order_routes.router)
app.include_router(payment_routes.router)
app.include_router(webhook_routes.router)
app.include_router(admin_order_routes.router)


@app.get("/health", tags=["infra"])
async def health():
    """Healthcheck. Usado por hosting/monitoramento."""
    return {"status": "ok"}