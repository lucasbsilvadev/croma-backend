from app.config.supabase import supabase_admin
from app.utils.exceptions import ConflictError


class ProfileRepository:
    """
    Único ponto de acesso à tabela `profiles`.
    Nenhuma query SQL fora daqui.
    """

    def get_by_user_id(self, user_id: str) -> dict | None:
        res = (
            supabase_admin.table("profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None
    def update(self, user_id: str, data: dict) -> dict:
        """Atualiza campos do profile. Usado pra backfill de cpf_cnpj."""
        res = (
            supabase_admin.table("profiles")
            .update(data)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0]
    
    def create(
        self,
        user_id: str,
        nome: str,
        cpf_cnpj: str | None = None,
    ) -> dict:
        """
        Cria um profile. Levanta ConflictError se já existir.
        Para criação idempotente (incluindo race conditions), use `ensure_profile`.
        """
        if self.get_by_user_id(user_id):
            raise ConflictError("Perfil já existe")

        row: dict = {"user_id": user_id, "nome": nome}
        if cpf_cnpj:
            from app.utils.validators import derive_tipo_pessoa
            row["cpf_cnpj"] = cpf_cnpj
            row["tipo_pessoa"] = derive_tipo_pessoa(cpf_cnpj)

        res = (
            supabase_admin.table("profiles")
            .insert(row)
            .execute()
        )
        return res.data[0]

    def ensure_profile(
        self,
        user_id: str,
        nome: str,
        cpf_cnpj: str | None = None,
    ) -> dict:
        """
        Garante que existe um profile para o user_id.
        Idempotente. Trata race conditions e CPF/CNPJ duplicado.
        """
        existing = self.get_by_user_id(user_id)

        if existing:
            # Backfill: profile criado sem cpf_cnpj (ex: user legado).
            # Se o request tem cpf_cnpj e o profile não, tenta atualizar.
            if cpf_cnpj and not existing.get("cpf_cnpj"):
                from app.utils.validators import derive_tipo_pessoa
                try:
                    return self.update(user_id, {
                        "cpf_cnpj": cpf_cnpj,
                        "tipo_pessoa": derive_tipo_pessoa(cpf_cnpj),
                    })
                except Exception as e:
                    code = getattr(e, "code", None)
                    if code == "23505":
                        # CPF já pertence a outro user
                        raise ConflictError("CPF/CNPJ já cadastrado")
                    raise
            return existing

        try:
            return self.create(user_id=user_id, nome=nome, cpf_cnpj=cpf_cnpj)
        except ConflictError:
            retry = self.get_by_user_id(user_id)
            if retry:
                return retry
            raise
        except Exception as e:
            code = getattr(e, "code", None)
            if code in ("23505", "23503"):
                retry = self.get_by_user_id(user_id)
                if retry:
                    return retry
                if code == "23505" and cpf_cnpj:
                    raise ConflictError("CPF/CNPJ já cadastrado")
            raise