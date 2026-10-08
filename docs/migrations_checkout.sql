-- 1. profiles: cpf_cnpj + tipo_pessoa
alter table public.profiles
  add column if not exists cpf_cnpj varchar,
  add column if not exists tipo_pessoa varchar
    check (tipo_pessoa in ('fisica','juridica'));

create unique index if not exists profiles_cpf_cnpj_uniq
  on public.profiles(cpf_cnpj) where cpf_cnpj is not null;

-- 2. orders: snapshot de endereço (operacional, não fiscal)
alter table public.orders
  add column if not exists address_snapshot jsonb;

-- 3. payment_events (idempotência de webhook)
create table if not exists public.payment_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null default 'mercadopago',
  external_event_id text not null,
  external_resource_id text,
  event_type text not null,
  payload jsonb not null,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint payment_events_provider_event_uniq
    unique (provider, external_event_id)
);

create index if not exists payment_events_external_resource_idx
  on public.payment_events(external_resource_id);
create index if not exists payment_events_unprocessed_idx
  on public.payment_events(created_at) where processed_at is null;

-- 4. orders: índice pra reconciliação
create index if not exists orders_payment_external_id_idx
  on public.orders(payment_external_id) where payment_external_id is not null;