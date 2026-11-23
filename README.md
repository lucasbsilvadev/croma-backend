# croma — backend

API FastAPI + supabase para a Croma Drip.

## requisitos

- python 3.12 (ou 3.11)
- conta no Supabase (gratuita)
- git

## setup local

### 1. clonar e criar venv

```bash
git clone <url-do-repo>
cd croma-backend
python -m venv .venv
```

ativar:
- **windows (powerShell):** `.venv\Scripts\Activate.ps1`
- **mac/linux:** `source .venv/bin/activate`

### 2. Instalar dependências

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 3. criar projeto no Supabase

1. acesse [supabase.com/dashboard](https://supabase.com/dashboard)
2. crie um projeto novo (qualquer nome, região mais próxima)
3. anote:
   - **project URL** (Settings → API → Project URL)
   - **anon public key** (Settings → API → Project API keys)
   - **service_role key** (Settings → API → Project API keys — é secreta)

### 4. configurar variáveis de ambiente

```bash
cp .env.example .env
```

preencha o `.env` com os valores do passo anterior.

### 5. rodar as migrações no Supabase

abra o **SQL Editor** no dashboard do Supabase e rode o conteúdo de
`docs/migrations.sql` (ou o script que o time te passar, caso o projeto tenha alteração não documentada nesse README.MD).

### 6. subir o servidor

```bash
uvicorn app.main:app --reload --port 8000
```

Acesse [http://localhost:8000/docs](http://localhost:8000/docs) pro Swagger.

### 7. Rodar os testes

```bash
pytest -v
```

Testes de integração (batem no Supabase real):

```bash
pytest -m integration -v
```

## estrutura

```
app/
├── config/       # Settings e clients Supabase
├── middleware/   # Auth, CORS, rate limit, request ID
├── models/       # Schemas Pydantic (contratos HTTP)
├── repositories/ # Acesso a dados (Supabase)
├── routes/       # Endpoints FastAPI
├── services/     # Regras de negócio
└── utils/        # Exceptions, logging, validators
```

fluxo: **route → service → repository → supabase**

## Convenções

- **preço:** sempre `Decimal` no Python, serializado como string no JSON
- **RBAC:** rotas `/admin/*` exigem `role='admin'`
- **soft delete:** `ativo=false`, nunca `DELETE` físico
- **logs:** JSON estruturado em `stdout` (eventos `AUTH_*`, `PRODUCT_*`,
  `ORDER_*`, `ADDRESS_*`, `SHIPPING_*`)
- **Migrations:** via SQL Editor do Supabase (não usamos Alembic ainda)

## documentação adicional

- [`docs/auth.md`](docs/auth.md) — decisões arquiteturais do módulo de auth
