# app/config/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    env: str = "dev"

    mp_access_token: str
    mp_public_key: str
    mp_webhook_secret: str
    mp_env: str = "sandbox"

    extra_cors_origins: str = ""

    mp_debug_errors: bool = False

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def is_mp_sandbox(self) -> bool:
        return self.mp_env == "sandbox"


settings = Settings()