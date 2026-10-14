# Termos & LGPD — Decisões Arquiteturais

Documento de decisões sobre termos de uso versionados e conformidade LGPD
do backend Croma Drip.

**Status do módulo:** 🚧 em implementação — bloco Termos + LGPD.

---

## Visão geral

O módulo de Termos de Uso versionados é a base de compliance jurídico da Croma.
Ele resolve três problemas:

1. **Prova de consentimento** — qual texto exato o usuário aceitou, e quando.
2. **Versionamento** — o jurídico publica uma nova versão sem deploy de backend.
3. **Fail-closed** — o backend nunca aceita uma versão que não conhece.

O backend **não armazena o texto dos termos**. Armazena a **versão** e o
**hash do texto** (`document_hash`). O texto vive onde o jurídico publicar
(hoje: placeholder no front; futuro: CMS ou markdown versionado).

---

## LGPD-01 — Termos de uso versionados com fonte da verdade no backend

**Status:** implementado e testado.

### Contexto

Antes desta decisão, `RegisterRequest.terms_version` era string livre. O front
podia mandar `"1.0"`, `"2025-01"`, `"banana"`, e o backend aceitava. O aceite
era gravado em `terms_acceptances` sem vínculo com uma versão canônica.
Isso viola "nunca confie no frontend" e enfraquece a prova de consentimento.

### Decisão

1. **Fonte da verdade é a tabela `terms_versions`** no Supabase, não uma
   constante no código. O jurídico pode publicar uma nova versão sem deploy
   de backend; o histórico fica auditável; o `document_hash` fica vinculado
   à versão.

2. **O front continua mandando `terms_version`** no `RegisterRequest`.
   O backend **valida contra `terms_versions`** no service. Versão inexistente
   ou inativa → `422` fail-closed.

3. **`GET /terms/current` é público** (sem auth) e devolve
   `{ version, effective_at, url }`. O front consome esse endpoint pra
   renderizar o link e montar o payload. O front **não hardcoda** a versão.

4. **`document_hash` é gravado no aceite** nesta sprint. No momento do
   register, o service lê `terms_versions.document_hash` da versão vigente
   e grava esse valor em `terms_acceptances.document_hash`. Isso prova qual
   texto exato foi aceito, não apenas qual versão.

5. **Formato da versão:** ISO date `YYYY-MM-DD` (ex: `2026-10-13`).
   Versões futuras seguem o mesmo formato. O nome é a data de publicação
   da versão.

6. **`terms_acceptances` ganha a coluna `document_hash`** (nullable, migration
   não-destrutiva). Aceites antigos ficam com `NULL` — não há como recuperar
   o texto aceito antes desta decisão.

### Rationale

- **Fail-closed:** versão desconhecida → 422. Nunca aceitar string livre.
- **Sem hardcode:** o backend não conhece versões em código; consulta a tabela.
- **Sem confiar no front:** o front manda a versão, mas quem decide se ela é
  válida é o backend.
- **Prova criptográfica:** `document_hash` no aceite é o mínimo de compliance
  sério. Sem ele, "aceitou v1" não prova nada se o texto de v1 mudar depois.

### Trade-offs

- **Uma query a mais no register.** O `register` já faz 1 chamada HTTP pro
  Supabase Auth, 1 insert de profile, 1 insert de aceite. Uma query a mais em
  `terms_versions` é ruído. O custo é aceitável pelo ganho de auditabilidade.
- **Tabela a mais pra gerenciar.** Admin precisa cadastrar a versão antes de
  publicar o termo. Aceitável: é o fluxo que o jurídico quer.
- **FK de `terms_acceptances.terms_version` → `terms_versions.version` fica
  fora.** A integridade é garantida no service. Evita migration destrutiva.
  Se um dia quisermos FK, é migration não-destrutiva depois.

### Fora desta decisão (registrado como tasks separadas)

- **LGPD-02** — ~~gravar `document_hash` no aceite~~ → **absorvido por LGPD-01**.
- **LGPD-03** — criptografia de campo em repouso (CPF/CNPJ, endereço).
- **LGPD-04** — Política de Privacidade versionada (mesmo mecanismo, tabela
  separada ou generalização de `terms_versions`).
- **LGPD-05** — consentimento de marketing (checkbox separado, revogável).
- **LGPD-06** — exclusão de conta / direito ao esquecimento.
- **LGPD-07** — exportação de dados (portabilidade).
- **LGPD-08** — audit log de acesso admin.

---

## LGPD-09 — Pseudonimização de exibição e sanitização global de logs

**Status:** implementado e testado.

### Contexto

CPF/CNPJ é dado pessoal armazenado (necessário para pagamento). Hoje:

- `/me` expõe `cpf_cnpj` completo.
- `_sanitize_log_string` cobre CPF/CNPJ/email **apenas no `MPClient`**.
  O resto do app loga o que quiser.
- Não há mascaramento de exibição no front.

### Decisão

1. **Backend — sanitização global de logs.** `_sanitize_log_string` e
   `_SENSITIVE_PATTERNS` saem de `app/infra/mp_client.py` e passam a viver
   em `app/utils/logging.py` (fonte única). O `JsonFormatter` aplica
   `_sanitize_log_string` em `message` e nos campos extras da allowlist
   **antes** de serializar. Assim, qualquer log do app é sanitizado, não só
   os do MPClient.

2. **Front — mascaramento de exibição.** CPF/CNPJ e email são mascarados na
   exibição (`***.***.777-**`, `a***@b.com`). O valor completo continua
   existindo no estado da aplicação (pra pré-preencher checkout, etc), mas
   nunca é renderizado em tela.

### Rationale

- **Defesa em profundidade:** mesmo que alguém esqueça de sanitizar um log
  específico, o formatter global pega.
- **Menor exposição visual:** reduz risco de shoulder surfing e screenshot
  acidental em telas de perfil/pedido.
- **Não é pseudonimização de armazenamento.** O dado em repouso continua
  completo. Isso é decisão separada (LGPD-03).

### Trade-offs

- **`JsonFormatter` mais caro.** Aplica regex em cada log. Irrelevante na
  escala da Croma.
- **Risco de mascarar demais.** Um log que legitimamente precisa do CPF
  completo (não existe hoje) ficaria inútil. Se aparecer, o campo tem que
  entrar na allowlist **e** justificar.

---

## LGPD-10 — Sanitização no `JsonFormatter` (implementação)

**Status:** implementado e testado.

`JsonFormatter.format` aplica `_sanitize_log_string` em:

- `record.getMessage()` → campo `message`
- Cada campo da allowlist (`event`, `request_id`, `user_id`, `endpoint`,
  `status`, `duration_ms`, `error`, `mp_error_detail`)

A allowlist continua sendo a barreira principal: campos fora dela são
descartados. A sanitização é a segunda barreira: campos que passam pela
allowlist são varridos por regex antes de sair.

---

## Configurações do Supabase

Tabelas criadas nesta sprint:

- `terms_versions` — versões publicadas dos termos.
- `terms_acceptances` — aceites dos usuários (existente; ganhou
  `document_hash`).

RLS:

- `terms_versions`: leitura pública de versões ativas; escrita só via
  `service_role`.
- `terms_acceptances`: leitura pelo próprio usuário; escrita só via
  `service_role`.

---

## O que NÃO pertence ao backend

- **Texto dos termos:** vive onde o jurídico publicar (placeholder no front
  nesta sprint).
- **Política de Privacidade:** LGPD-04, separado.
- **Exclusão de conta:** LGPD-06, separado.
- **Exportação de dados:** LGPD-07, separado.