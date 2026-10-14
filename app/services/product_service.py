from decimal import Decimal

from app.infra.cloudinary_client import CloudinaryClient
from app.repositories.product_repository import ProductRepository
from app.utils.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ProductService:
    """
    Regras de negócio de produtos.
    """

    # ============================================================
    # Constantes de upload (validação fail-fast)
    # ============================================================
    IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
    IMAGE_ALLOWED_MIME = frozenset({
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    })

    def __init__(
        self,
        product_repo: ProductRepository | None = None,
        cloudinary: CloudinaryClient | None = None,
    ):
        self.product_repo = product_repo or ProductRepository()
        self.cloudinary = cloudinary or CloudinaryClient()

    # ============================================================
    # Público
    # ============================================================

    def list_active(self) -> list[dict]:
        """Lista produtos ativos com suas imagens."""
        products = self.product_repo.list_active()
        return [self._hydrate(p) for p in products]

    def get_active_by_slug(self, slug: str) -> dict:
        """Retorna produto ativo pelo slug. 404 se não existir ou inativo."""
        product = self.product_repo.get_by_slug(slug)

        if not product or not product.get("ativo"):
            raise NotFoundError("Produto não encontrado")

        return self._hydrate(product)

    # ============================================================
    # Admin
    # ============================================================

    def get_by_id_any_status(self, product_id: str) -> dict:
        """
        Retorna produto por ID, independente de estar ativo.
        Usado pelas rotas admin (detalhe + form de edição).

        404 se não existir. Não filtra por `ativo` — admin precisa
        enxergar inativos pra reativar/editar.
        """
        product = self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Produto não encontrado")
        return self._hydrate(product)

    def create_product(self, data: dict) -> dict:
        """
        Cria produto. Valida slug único.
        """
        slug = data["slug"]

        if self.product_repo.exists_slug(slug):
            logger.info(
                "Create product falhou: slug duplicado",
                extra={"event": "PRODUCT_CREATE_FAILED", "error": "duplicate_slug"},
            )
            raise ConflictError("Slug já existe")

        preco = data["preco"]
        if not isinstance(preco, Decimal):
            preco = Decimal(str(preco))

        payload = {
            "nome": data["nome"],
            "slug": slug,
            "descricao": data.get("descricao"),
            "preco": str(preco),
            "estoque": data.get("estoque", 0),
            "ativo": True,
        }

        product = self.product_repo.create(payload)

        logger.info(
            "Produto criado",
            extra={"event": "PRODUCT_CREATED"},
        )

        return self._hydrate(product)

    def list_all(self) -> list[dict]:
        """Lista todos (admin). Inclui inativos."""
        products = self.product_repo.list_all()
        return [self._hydrate(p) for p in products]

    def update_product(self, product_id: str, data: dict) -> dict:
        """Atualização parcial. Só campos enviados."""
        existing = self.product_repo.get_by_id(product_id)
        if not existing:
            raise NotFoundError("Produto não encontrado")

        # Filtra None (não enviado) e serializa Decimal
        payload = {}
        for key, value in data.items():
            if value is None:
                continue
            if key == "preco" and isinstance(value, Decimal):
                payload[key] = str(value)
            else:
                payload[key] = value

        if not payload:
            return self._hydrate(existing)

        updated = self.product_repo.update(product_id, payload)

        logger.info(
            "Produto atualizado",
            extra={"event": "PRODUCT_UPDATED"},
        )

        return self._hydrate(updated)

    def soft_delete(self, product_id: str) -> dict:
        """Soft delete: ativo = false."""
        existing = self.product_repo.get_by_id(product_id)
        if not existing:
            raise NotFoundError("Produto não encontrado")

        deleted = self.product_repo.soft_delete(product_id)

        logger.info(
            "Produto desativado",
            extra={"event": "PRODUCT_SOFT_DELETED"},
        )

        return self._hydrate(deleted)

    # ============================================================
    # Imagens
    # ============================================================

    def add_image(self, product_id: str, url: str, position: int) -> dict:
        """
        Associa uma URL de imagem já existente ao produto.

        Diferente de `add_image_from_upload`: aquele recebe bytes e faz
        upload pro storage. Este recebe a URL pronta (útil para
        reimportar catálogo, seeds, testes, etc).
        """
        existing = self.product_repo.get_by_id(product_id)
        if not existing:
            raise NotFoundError("Produto não encontrado")

        image = self.product_repo.add_image(product_id, url, position)

        logger.info(
            "Imagem adicionada",
            extra={"event": "PRODUCT_IMAGE_ADDED"},
        )

        return image

    def add_image_from_upload(
        self,
        *,
        product_id: str,
        file_bytes: bytes,
        content_type: str,
        position: int,
    ) -> dict:
        """
        Sobe uma imagem pro storage e persiste a URL em product_images.

        Validações (fail-fast, antes de gastar banda com o Cloudinary):
        - produto existe
        - content_type permitido
        - arquivo não vazio
        - arquivo <= IMAGE_MAX_BYTES
        """
        existing = self.product_repo.get_by_id(product_id)
        if not existing:
            raise NotFoundError("Produto não encontrado")

        if content_type not in self.IMAGE_ALLOWED_MIME:
            raise ValidationError(
                f"Tipo de arquivo não permitido: "
                f"{content_type or 'desconhecido'}. "
                f"Aceitos: JPG, PNG, WEBP, GIF."
            )

        if not file_bytes:
            raise ValidationError("Arquivo vazio")

        if len(file_bytes) > self.IMAGE_MAX_BYTES:
            mb = self.IMAGE_MAX_BYTES // (1024 * 1024)
            raise ValidationError(f"Arquivo muito grande. Máximo: {mb} MB.")

        uploaded = self.cloudinary.upload_product_image(
            file_bytes=file_bytes,
            product_id=product_id,
        )

        image = self.product_repo.add_image(
            product_id, uploaded["url"], position
        )

        logger.info(
            "Imagem enviada",
            extra={"event": "PRODUCT_IMAGE_UPLOADED"},
        )

        return image

    def remove_image(self, product_id: str, image_id: str) -> None:
        image = self.product_repo.get_image(image_id)
        if not image or image["product_id"] != product_id:
            raise NotFoundError("Imagem não encontrada")

        self.product_repo.remove_image(image_id)

        logger.info(
            "Imagem removida",
            extra={"event": "PRODUCT_IMAGE_REMOVED"},
        )

    # ============================================================
    # Helpers
    # ============================================================

    def _hydrate(self, product: dict) -> dict:
        """Adiciona imagens ao produto. Usado em todas as respostas."""
        images = self.product_repo.list_images(product["id"])
        return {**product, "imagens": images}