# app/config/settings.py

from urllib.parse import urlparse

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

    # ----- Cloudinary -----
    # Formato recomendado (Cloudinary): cloudinary://<key>:<secret>@<cloud_name>
    # Se presente, tem prioridade sobre o trio abaixo.
    cloudinary_url: str | None = None

    # Fallback: credenciais em campos separados.
    # Opcional agora que CLOUDINARY_URL existe.
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None

    cloudinary_folder: str = "croma/products"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def is_mp_sandbox(self) -> bool:
        return self.mp_env == "sandbox"

    def get_cloudinary_credentials(self) -> dict:
        """
        Resolve as credenciais do Cloudinary a partir de CLOUDINARY_URL
        ou, em fallback, dos 3 campos separados.

        Levanta ValueError se nenhum dos dois formatos estiver preenchido
        — fail-closed: sem credenciais, o app não deve subir silenciosamente
        e falhar só no primeiro upload.
        """
        if self.cloudinary_url:
            return self._parse_cloudinary_url(self.cloudinary_url)

        if all(
            [self.cloudinary_cloud_name, self.cloudinary_api_key, self.cloudinary_api_secret]
        ):
            return {
                "cloud_name": self.cloudinary_cloud_name,
                "api_key": self.cloudinary_api_key,
                "api_secret": self.cloudinary_api_secret,
            }

        raise ValueError(
            "Cloudinary não configurado. Defina CLOUDINARY_URL "
            "(formato cloudinary://<api_key>:<api_secret>@<cloud_name>) "
            "ou o trio CLOUDINARY_CLOUD_NAME + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET."
        )

    @staticmethod
    def _parse_cloudinary_url(url: str) -> dict:
        """Parseia cloudinary://<api_key>:<api_secret>@<cloud_name>."""
        parsed = urlparse(url)
        if parsed.scheme != "cloudinary":
            raise ValueError(
                "CLOUDINARY_URL inválido: precisa começar com 'cloudinary://'"
            )
        if not (parsed.username and parsed.password and parsed.hostname):
            raise ValueError(
                "CLOUDINARY_URL inválido: esperado formato "
                "cloudinary://<api_key>:<api_secret>@<cloud_name>"
            )
        return {
            "cloud_name": parsed.hostname,
            "api_key": parsed.username,
            "api_secret": parsed.password,
        }


settings = Settings()