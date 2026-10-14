# app/infra/cloudinary_client.py
"""
Cliente HTTP/SDK do Cloudinary.

Responsabilidade ÚNICA: encapsular comunicação com o Cloudinary.
Não contém regra de negócio (isso é do ProductService).
"""
from io import BytesIO
from uuid import uuid4

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinarySDKError

from app.config.settings import settings
from app.utils.exceptions import StorageError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CloudinaryClient:
    """Encapsula uploads/operações no Cloudinary."""

    def __init__(
        self,
        cloud_name: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        folder: str | None = None,
    ):
        # Prioridade:
        #   1. Parâmetros explícitos (útil em testes)
        #   2. settings.get_cloudinary_credentials() (CLOUDINARY_URL ou trio)
        if cloud_name and api_key and api_secret:
            self.cloud_name = cloud_name
            self.api_key = api_key
            self.api_secret = api_secret
        else:
            creds = settings.get_cloudinary_credentials()
            self.cloud_name = creds["cloud_name"]
            self.api_key = creds["api_key"]
            self.api_secret = creds["api_secret"]

        self.folder = (folder or settings.cloudinary_folder).strip("/")

        cloudinary.config(
            cloud_name=self.cloud_name,
            api_key=self.api_key,
            api_secret=self.api_secret,
            secure=True,
        )

    def upload_product_image(
        self,
        *,
        file_bytes: bytes,
        product_id: str,
    ) -> dict:
        """
        Sobe bytes pro Cloudinary.

        Retorna { url, public_id }. O caller (service) decide o que fazer
        com esses campos. Não valida MIME nem tamanho — isso é regra de
        negócio e vive no ProductService.
        """
        public_id = f"{self.folder}/{product_id}/{uuid4().hex}"

        try:
            result = cloudinary.uploader.upload(
                BytesIO(file_bytes),
                public_id=public_id,
                resource_type="image",
                overwrite=False,
                invalidate=True,
            )
        except CloudinarySDKError as e:
            logger.warning(
                "Cloudinary upload falhou",
                extra={
                    "event": "CLOUDINARY_UPLOAD_FAILED",
                    "error": type(e).__name__,
                },
            )
            raise StorageError("Falha ao subir imagem no storage") from e

        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
        }