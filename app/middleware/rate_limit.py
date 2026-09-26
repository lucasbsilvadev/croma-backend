from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

RATE_LIMITS = {
    "login": "10/minute",
    "register": "5/minute",
    "forgot_password": "3/minute",
}