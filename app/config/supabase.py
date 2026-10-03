from supabase import Client, create_client

from app.config.settings import settings

# Client público: usa anon key, respeita RLS.
# Usar para tudo que é "em nome do usuário".
supabase_public: Client = create_client(
    settings.supabase_url, settings.supabase_anon_key
)

# Client admin: usa service key, bypassa RLS.
# Usar SÓ no backend e SÓ quando estritamente necessário (ex: criar profile após signup).
# NUNCA expor essa key no front.
supabase_admin: Client = create_client(
    settings.supabase_url, settings.supabase_service_key
)
