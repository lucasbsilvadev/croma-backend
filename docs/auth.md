# Autenticação — Decisões Arquiteturais

Documento de decisões sobre os fluxos de auth do backend Croma Drip.

---

## AUTH-01: Cadastro

**Status:** implementado e testado.

- Endpoint: `POST /auth/register`
- Backend chama Supabase Auth via `httpx` direto em `/auth/v1/signup`
- Após signup, cria registro em `profiles` via `ProfileRepository`
- Validações: nome (2-100), email (EmailStr), password (8-72)
- Rate limit: 5/min por IP
- Testado: unitário (mock `httpx`) + integração (Supabase real) + manual (Swagger)

---

## AUTH-02: Login

**Status:** implementado e testado.

- Endpoint: `POST /auth/login`
- Backend chama Supabase Auth via `httpx` direto em `/auth/v1/token?grant_type=password`
- Retorna `access_token` + `refresh_token`
- Rate limit: 10/min por IP
- Endpoint protegido: `GET /me` valida JWT via `get_current_user`
- Validação do JWT: `GET /auth/v1/user` do Supabase (stateless do ponto de vista do backend)
- Testado: unitário + integração + manual

---

## AUTH-03: Logout

**Status:** stateless — sem código no backend.

**Decisão:** o logout é responsabilidade do frontend via SDK do Supabase.

**Fluxo:**
1. Front chama `supabase.auth.signOut()`
2. Supabase invalida o `refresh_token` no servidor
3. O `access_token` (JWT) expira naturalmente em 1h

**Por que não expor `POST /auth/logout`:**
- O SDK do Supabase já cobre o caso de uso
- Um endpoint exigiria o backend receber e repassar o refresh token,
  adicionando superfície sem ganho real para o MVP
- Revogação global (todos os dispositivos) é feature separada, fora do MVP

**Front:**
```js
await supabase.auth.signOut()
```

**Referência:** https://supabase.com/docs/reference/javascript/auth-signout

---

## AUTH-04: Sessão persistente

**Status:** stateless — sem código no backend.

**Decisão:** o SDK do Supabase persiste a sessão automaticamente.

**Como funciona:**
- O SDK armazena `access_token` + `refresh_token` em `localStorage` (web)
- No boot da aplicação, o front chama `supabase.auth.getSession()`
- Se a sessão existir e o access token estiver expirado, o SDK renova
  automaticamente usando o refresh token
- O front observa mudanças via `supabase.auth.onAuthStateChange()`

**O que o backend precisa:**
- Apenas validar o `access_token` recebido em cada request (feito via `get_current_user`)
- Nada mais. Sem tabela de sessão, sem mecanismo paralelo.

**Front:**
```js
const { data: { session } } = await supabase.auth.getSession()
if (session) {
  // usuário está autenticado
}
```

**Referência:** https://supabase.com/docs/reference/javascript/auth-getsession

---

## AUTH-05: Login com Google (OAuth)

**Status:** stateless — sem código no backend.

**Decisão:** Supabase Auth gerencia o fluxo OAuth completo. O backend só
valida o JWT resultante — o mesmo `get_current_user` já cobre.

**Fluxo:**
1. Front chama `supabase.auth.signInWithOAuth({ provider: 'google' })`
2. Supabase redireciona o usuário pro Google
3. Usuário autoriza
4. Google redireciona de volta pro front com um `code`
5. Supabase troca o `code` por uma sessão (`access_token` + `refresh_token`)
6. O `access_token` emitido é um JWT **idêntico em formato** ao emitido por
   email/senha. O `get_current_user` já valida.

**Configuração necessária (Supabase Dashboard):**
- Authentication → Providers → Google → habilitar
- Inserir Client ID e Client Secret (do Google Cloud Console)

**Front:**
```js
await supabase.auth.signInWithOAuth({ provider: 'google' })
```

**Referência:** https://supabase.com/docs/guides/auth/social-login/auth-google

---

## Configurações do Supabase Dashboard

Config atual do projeto:

- **Confirm email:** DESLIGADO em dev (ligar em produção)
- **Sign ups:** habilitado
- **Password mínimo:** 6 (validado também no backend: 8)
- **JWT expiry:** 3600s (1h) — padrão

**TODO para produção:**
- [ ] Ligar "Confirm email"
- [ ] Configurar SMTP customizado (Croma enviar emails via domínio próprio)
- [ ] Configurar Redirect URLs com `cromadrip.com.br`
- [ ] Considerar OAuth Google (AUTH-05)