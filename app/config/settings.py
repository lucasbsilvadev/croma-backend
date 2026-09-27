from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações carregadas de variáveis de ambiente / .env.
    Falha na inicialização se algo obrigatório faltar — melhor quebrar no boot
    do que descobrir em runtime.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    env: str = "dev"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


settings = Settings()