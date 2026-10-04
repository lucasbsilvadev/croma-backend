# Croma Drip — Backend

API FastAPI + Supabase para a Croma Drip.

## Requisitos

- Python 3.12 (ou 3.11)
- Conta no Supabase (gratuita)
- Git

## Setup local

### 1. Clonar e criar venv

```bash
git clone <url-do-repo>
cd croma-backend
python -m venv .venv
```

Ativar:
- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **Mac/Linux:** `source .venv/bin/activate`

### 2. Instalar dependências

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 3. Criar projeto no Supabase

1. Acesse [supabase.com/dashboard](https://supabase.com/dashboard)
2. Crie um projeto novo (qualquer nome, região mais próxima)
3. Anote:
   - **Project URL** (Settings → API → Project URL)
   - **anon public key** (Settings → API → Project API keys)
   - **service_role key** (Settings → API → Project API keys — é secreta)

### 4. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Preencha o `.env` com os valores do passo anterior.

### 5. Rodar as migrações no Supabase

Abra o **SQL Editor** no dashboard do Supabase e rode o conteúdo de
`docs/migrations.sql` (ou o script que o time te passar).

### 6. Subir o servidor

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

## Estrutura

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

Fluxo: **Route → Service → Repository → Supabase**

## Convenções

- **Preço:** sempre `Decimal` no Python, serializado como string no JSON
- **RBAC:** rotas `/admin/*` exigem `role='admin'`
- **Soft delete:** `ativo=false`, nunca `DELETE` físico
- **Logs:** JSON estruturado em `stdout` (eventos `AUTH_*`, `PRODUCT_*`,
  `ORDER_*`, `ADDRESS_*`, `SHIPPING_*`)
- **Migrations:** via SQL Editor do Supabase (não usamos Alembic ainda)

## Documentação adicional

- [`docs/auth.md`](docs/auth.md) — decisões arquiteturais do módulo de auth