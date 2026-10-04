# Autenticação — Decisões Arquiteturais

Documento de decisões sobre os fluxos de auth do backend Croma Drip.

**Status do módulo:** ✅ encerrado para o MVP.

---

## Visão geral

O backend **não implementa auth do zero**. Delega ao Supabase Auth (GoTrue) e
se responsabiliza por:

1. Validar JWTs emitidos pelo Supabase em cada request autenticado.
2. Garantir que um `profile` exista na nossa tabela `profiles` (idempotente).
3. Aplicar política de senha forte no cadastro.
4. Logar eventos de segurança de forma estruturada, sem vazar credenciais.

Tudo que é sessão, refresh token, revogação e OAuth é gerenciado pelo Supabase.

---

## AUTH-01: Cadastro (register)

**Status:** implementado e testado (unitário + integração + manual).

- Endpoint: `POST /auth/register`
- Backend chama Supabase Auth via `httpx` direto em `/auth/v1/signup`
  (não usa o SDK por bug conhecido do `supabase-py 2.31`).
- Após signup, chama `ProfileRepository.ensure_profile(...)` — idempotente.
- Validações:
  - `nome`: 2-100 chars
  - `email`: `EmailStr`
  - `password`: 8-72 chars + política forte (ver AUTH-06)
- Rate limit: 5/min por IP
- Logs: `AUTH_REGISTER_SUCCESS`, `AUTH_REGISTER_FAILED` (com `error` estrutural,
  nunca o payload).
- Testado: unitário (mock `httpx`) + integração (Supabase real) + manual.

---

## AUTH-02: Login

**Status:** implementado e testado.

- Endpoint: `POST /auth/login`
- Backend chama Supabase Auth via `httpx` direto em
  `/auth/v1/token?grant_type=password`.
- Retorna `access_token` + `refresh_token`.
- **Política de senha NÃO se aplica aqui** — usuário pode ter senha antiga
  criada antes da política. Validar no login travaria contas legítimas.
- Rate limit: 10/min por IP
- Logs: `AUTH_LOGIN_SUCCESS` (com `user_id`), `AUTH_LOGIN_FAILED` (genérico,
  sem email — evita enumeração de usuários via inspeção de log).
- Testado: unitário + integração + manual.

---

## AUTH-03: Logout

**Status:** stateless — sem código no backend.

**Decisão:** o logout é responsabilidade do frontend via SDK do Supabase.

**Fluxo:**
1. Front chama `supabase.auth.signOut()`.
2. Supabase invalida o `refresh_token` no servidor.
3. O `access_token` (JWT) expira naturalmente em 1h.

**Por que não expor `POST /auth/logout`:**
- O SDK do Supabase já cobre o caso de uso.
- Um endpoint exigiria o backend receber e repassar o refresh token,
  adicionando superfície sem ganho real para o MVP.
- Revogação global (todos os dispositivos) é feature separada, fora do MVP.

**Referência:** https://supabase.com/docs/reference/javascript/auth-signout

---

## AUTH-04: Sessão persistente

**Status:** stateless — sem código no backend.

**Decisão:** o SDK do Supabase persiste a sessão automaticamente.

- O SDK armazena `access_token` + `refresh_token` em `localStorage` (web).
- No boot da aplicação, o front chama `supabase.auth.getSession()`.
- Se a sessão existir e o access token estiver expirado, o SDK renova
  automaticamente usando o refresh token.
- O front observa mudanças via `supabase.auth.onAuthStateChange()`.

**O que o backend precisa:** apenas validar o `access_token` recebido em cada
request (feito via `get_current_user`). Nada mais. Sem tabela de sessão, sem
mecanismo paralelo.

**Referência:** https://supabase.com/docs/reference/javascript/auth-getsession

---

## AUTH-05: Login com Google (OAuth)

**Status:** backend pronto; configuração de provider é external.

**Decisão arquitetural:** o backend **não intermedia** OAuth. O Supabase
gerencia o fluxo completo. O backend só valida o JWT resultante — que é
idêntico em formato ao JWT emitido por email/senha.

**Fluxo:**

1. Front chama `supabase.auth.signInWithOAuth({ provider: 'google' })`
2. Supabase redireciona o usuário pro Google
3. Usuário autoriza
4. Google devolve pro Supabase um `code`
5. Supabase troca o `code` por uma sessão (`access_token` + `refresh_token`)
6. Front usa o `access_token` em requests ao backend
7. Backend: `get_current_user()`
   - valida o JWT via `/auth/v1/user` do Supabase ✓
   - busca o profile em `profiles`
   - se não existir (primeiro login do usuário):
     - extrai o nome do `user_metadata` (Google preenche `full_name`)
     - chama `ensure_profile` (idempotente)
     - loga `AUTH_OAUTH_PROFILE_CREATED`

**Configuração externa necessária:**

Supabase Dashboard:
- Authentication → Providers → Google → habilitar.
- Colar Client ID e Client Secret do Google Cloud Console.
- Authentication → URL Configuration → adicionar redirect URLs
  (localhost de dev + domínio de produção).

Google Cloud Console:
- Criar OAuth 2.0 Client ID do tipo "Web application".
- Authorized redirect URI: `https://<project-ref>.supabase.co/auth/v1/callback`

**Backend:** zero configuração. Nada a adicionar em `.env`. O
`get_current_user` já cobre o caso.

**Referência:** https://supabase.com/docs/guides/auth/social-login/auth-google

---

## AUTH-06: Política de senha forte

**Status:** implementado e testado.

Aplicada **apenas** em criação/alteração de senha, **nunca** em login.

**Regras:**
- 8-72 caracteres (72 = limite do hash bcrypt do Supabase).
- Pelo menos 1 letra maiúscula.
- Pelo menos 1 letra minúscula.
- Pelo menos 1 dígito.
- Pelo menos 1 caractere especial.

**Onde vive:** `app/utils/validators.py` (função `is_strong_password`) +
validador Pydantic em `RegisterRequest`. A validação acontece **no boundary
HTTP** — antes de chegar no `AuthService`.

**Mensagem de erro:** exposta em `PASSWORD_RULES_MESSAGE`, reutilizável
pelo frontend.

**Testes:** `tests/auth/test_register.py` cobre cada regra individualmente
(sem maiúscula, sem minúscula, sem número, sem especial, curta, longa,
limites exatos de 8 e 72).

---

## AUTH-07: Validação de token em endpoints protegidos

**Status:** implementado e testado.

**Dependência:** `get_current_user` em `app/middleware/auth.py`.

**Entrada:** header `Authorization: Bearer <access_token>`.

**Fluxo:**
1. Se header ausente/vazio → `AuthError` (401).
2. Chama `GET /auth/v1/user` do Supabase (valida o JWT).
3. Se Supabase rejeita → `AuthError` (401) + log `AUTH_TOKEN_INVALID`.
4. Se resposta vem sem `user_id` → `AuthError` (401) + log.
5. Busca o `profile` em `profiles`.
6. Se profile não existe → `ensure_profile` (cobre OAuth first-access) +
   log `AUTH_OAUTH_PROFILE_CREATED`.
7. Retorna `{'user_id', 'email', 'role'}`.

**Authorization:** `get_current_admin_user` rejeita qualquer `role != "admin"`.
Fail-closed: role ausente ou inesperada → 403.

**Testado:** `tests/middleware/test_auth.py` cobre:
- Credenciais ausentes/vazias
- Token inválido (Supabase 401)
- Falha de rede
- Resposta sem `user_id`
- Profile existente → retorna direto
- Profile ausente → cria via `ensure_profile`
- `ensure_profile` devolvendo `None` → erro claro (não esconde bug)
- Nunca loga o token (em nenhum caminho)
- `get_current_admin_user`: aceita admin, rejeita user / role ausente /
  role desconhecida

---

## AUTH-08: Logging estruturado

**Status:** implementado e testado.

**Formato:** JSON (uma linha por evento) em `stdout`. Formatter em
`app/utils/logging.py`. Configurado no boot via `setup_logging()` em
`app/main.py`.

**Campos por evento:**

```json
{
  "timestamp": "2026-...T...:...+00:00",
  "level": "INFO",
  "logger": "app.services.auth_service",
  "message": "Login bem-sucedido",
  "event": "AUTH_LOGIN_SUCCESS",
  "request_id": "...",
  "user_id": "..."
}
```

**Allowlist de campos extras:** apenas `event`, `request_id`, `user_id`,
`endpoint`, `status`, `duration_ms`, `error`. Qualquer outro campo passado
via `extra={}` é **silenciosamente descartado** — isso garante que
`logger.info(..., extra={"password": "..."})` nunca vaze credencial.

**Eventos definidos:**
- `AUTH_REGISTER_SUCCESS` / `AUTH_REGISTER_FAILED`
- `AUTH_LOGIN_SUCCESS` / `AUTH_LOGIN_FAILED`
- `AUTH_TOKEN_INVALID`
- `AUTH_OAUTH_PROFILE_CREATED`
- `AUTH_FORGOT_PASSWORD_REQUESTED` / `AUTH_FORGOT_PASSWORD_FAILED`

**Nunca logado:**
- Password (em nenhuma forma)
- `access_token` / `refresh_token`
- Header `Authorization`
- Email completo em falha de login (evita enumeração via log)
- `SUPABASE_SERVICE_KEY`
- Client Secret do Google

---

## AUTH-09: Request ID

**Status:** implementado e testado.

**Middleware:** `app/middleware/request_id.py`.

- Gera um UUID v4 por request (ou propaga `X-Request-ID` se o cliente enviar).
- Guarda em `request.state.request_id`.
- Devolve no header `X-Request-ID` da resposta.
- Todos os logs do request usam o mesmo `request_id`.

**Propósito:** correlacionar `LOGIN → /me → CREATE ORDER → PAYMENT` quando
começarmos a desenvolver checkout.

---

## AUTH-10: Profile lifecycle (`ensure_profile`)

**Status:** implementado e testado.

**Localização:** `app/repositories/profile_repository.py`.

**Contrato:** `ensure_profile(user_id, nome) -> dict`

Idempotente. Garante que existe um profile, criando se necessário.

**Trata race conditions:**
- `23505` (unique violation) — outro request criou entre o `get` e o
  `insert`. Refaz o `get` e retorna o profile do vencedor.
- `23503` (FK violation) — o `user_id` ainda não commitou em `auth.users`
  (race do GoTrue). Refaz o `get`.
- `ConflictError` (nossa checagem antes do insert) — mesmo tratamento.

**Não esconde bugs:** qualquer outro erro propaga. Se o retry não encontra
o profile, propaga o erro original (não inventa sucesso).

**Testado:** `tests/repositories/test_profile_repository.py` cobre todos os
caminhos, incluindo:
- Idempotência em múltiplas chamadas (5 chamadas → 1 insert)
- Race com `ConflictError`
- Race com `23505`
- Race com `23503`
- Propagação de erro desconhecido (`42P01`)
- Propagação quando retry ainda não acha

---

## AUTH-11: Forgot password

**Status:** implementado e testado.

- Endpoint: `POST /auth/forgot-password`
- Backend chama Supabase `/auth/v1/recover` via `httpx`.
- Rate limit: 3/min por IP
- **Sempre retorna a mesma mensagem pública**
  (`"Se o email existir, enviaremos instruções"`), independente de o email
  existir ou não — evita enumeração de usuários via endpoint.
- Se a chamada externa falhar, logamos `AUTH_FORGOT_PASSWORD_FAILED`
  internamente (com `error` estrutural) mas **não propagamos** o erro. O
  cliente nunca sabe se falhou por rede ou se o email não existe.
- Testado: `tests/auth/test_auth_service.py` cobre sucesso, falha de rede
  silenciosa, e que o email sempre vai no payload.

---

## Configurações do Supabase Dashboard

Config atual do projeto (dev):

- **Confirm email:** DESLIGADO em dev.
- **Sign ups:** habilitado.
- **Password mínimo:** 6 (validado também no backend: 8 + política forte).
- **JWT expiry:** 3600s (1h) — padrão.

**TODO para produção:**
- [ ] Ligar "Confirm email".
- [ ] Configurar SMTP customizado (Croma enviando via domínio próprio).
- [ ] Configurar Redirect URLs com `cromadrip.com.br`.
- [ ] Habilitar provider Google (AUTH-05).

---

## O que NÃO pertence ao backend

- **Logout:** SDK do Supabase (AUTH-03).
- **Refresh de token:** SDK do Supabase (AUTH-04).
- **Fluxo OAuth:** Supabase Auth + Google (AUTH-05).
- **Hash de senha:** Supabase Auth.
- **Tabela de sessões:** Supabase Auth.

O backend é "stateless do ponto de vista de sessão": só valida JWT e
gerencia o domínio (profiles, futuramente produtos/pedidos).