from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações carregadas de variáveis de ambiente / .env.
    Falha na inicialização se algo obrigatório faltar — melhor quebrar no boot
    do que descobrir em runtime.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # ambiente
    env: str = "dev"

    # Mercado Pago
    mp_access_token: str
    mp_public_key: str
    mp_webhook_secret: str
    mp_env: str = "sandbox"

    # frontend teste
    extra_cors_origins: str = ""

    # Flag de diagnóstico: quando true, loga detalhe sanitizado
    # do erro retornado pelo Mercado Pago. Independe de MP_ENV.
    mp_debug_errors: bool = False

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def is_mp_sandbox(self) -> bool:
        return self.mp_env == "sandbox"


settings = Settings()