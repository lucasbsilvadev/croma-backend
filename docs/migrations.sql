-- ============================================================
-- Croma Drip — Schema completo (rodar do zero em banco novo)
-- ============================================================

-- 1. Profiles
create table if not exists public.profiles (
  id uuid not null default gen_random_uuid(),
  user_id uuid not null unique,
  nome varchar not null check (char_length(trim(nome)) >= 2),
  role text not null default 'user' check (role in ('user', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_pkey primary key (id),
  constraint profiles_user_id_fkey foreign key (user_id) references auth.users(id)
);

-- 2. Addresses
create table if not exists public.addresses (
  id uuid not null default gen_random_uuid(),
  user_id uuid not null,
  nome_destinatario varchar not null,
  cep varchar not null,
  logradouro varchar not null,
  numero varchar,
  complemento varchar,
  bairro varchar not null,
  cidade varchar not null,
  estado varchar not null,
  principal boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint addresses_pkey primary key (id),
  constraint addresses_user_id_fkey foreign key (user_id) references auth.users(id)
);

-- 3. Products
create table if not exists public.products (
  id uuid not null default gen_random_uuid(),
  nome varchar not null,
  slug varchar not null unique,
  descricao text,
  preco numeric not null check (preco > 0),
  ativo boolean not null default true,
  estoque integer not null default 0 check (estoque >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint products_pkey primary key (id)
);

-- 4. Product images
create table if not exists public.product_images (
  id uuid not null default gen_random_uuid(),
  product_id uuid not null,
  url text not null,
  position integer not null default 0,
  created_at timestamptz not null default now(),
  constraint product_images_pkey primary key (id),
  constraint product_images_product_id_fkey foreign key (product_id) references public.products(id)
);

-- 5. Shipping zones
create table if not exists public.shipping_zones (
  id uuid not null default gen_random_uuid(),
  nome text not null,
  cep_prefixo_min text not null,
  cep_prefixo_max text not null,
  valor_cents integer not null,
  prazo_dias integer not null,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  constraint shipping_zones_pkey primary key (id)
);

-- 6. Orders
create table if not exists public.orders (
  id uuid not null default gen_random_uuid(),
  user_id uuid not null,
  address_id uuid,
  status varchar not null default 'created'
    check (status in ('created','paid','production','shipped','delivered','cancelled')),
  subtotal numeric not null check (subtotal >= 0),
  frete numeric not null default 0 check (frete >= 0),
  total numeric not null check (total >= 0),
  notes text,
  payment_method text check (payment_method in ('pix','credit_card','manual')),
  payment_status text not null default 'pending'
    check (payment_status in ('pending','paid','failed','refunded')),
  payment_external_id text,
  paid_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint orders_pkey primary key (id),
  constraint orders_user_id_fkey foreign key (user_id) references auth.users(id),
  constraint orders_address_id_fkey foreign key (address_id) references public.addresses(id)
);

-- 7. Order items
create table if not exists public.order_items (
  id uuid not null default gen_random_uuid(),
  order_id uuid not null,
  product_id uuid not null,
  quantidade integer not null check (quantidade > 0),
  preco_unitario numeric not null check (preco_unitario > 0),
  product_nome text not null,
  product_slug text not null,
  constraint order_items_pkey primary key (id),
  constraint order_items_order_id_fkey foreign key (order_id) references public.orders(id),
  constraint order_items_product_id_fkey foreign key (product_id) references public.products(id)
);

-- ============================================================
-- Índices
-- ============================================================
create index if not exists products_ativo_idx on public.products(ativo) where ativo = true;
create index if not exists addresses_cep_idx on public.addresses(cep);
create index if not exists order_items_order_id_idx on public.order_items(order_id);
create index if not exists product_images_product_id_idx on public.product_images(product_id);
create index if not exists orders_user_id_idx on public.orders(user_id);
create index if not exists orders_status_idx on public.orders(status);

-- ============================================================
-- Trigger de updated_at
-- ============================================================
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists profiles_updated_at on public.profiles;
create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function set_updated_at();

drop trigger if exists addresses_updated_at on public.addresses;
create trigger addresses_updated_at
  before update on public.addresses
  for each row execute function set_updated_at();

drop trigger if exists products_updated_at on public.products;
create trigger products_updated_at
  before update on public.products
  for each row execute function set_updated_at();

drop trigger if exists orders_updated_at on public.orders;
create trigger orders_updated_at
  before update on public.orders
  for each row execute function set_updated_at();

-- ============================================================
-- Seed: shipping zones (DF ajustado)
-- ============================================================
insert into public.shipping_zones (nome, cep_prefixo_min, cep_prefixo_max, valor_cents, prazo_dias)
values
  ('DF',             '70000000', '73699999', 1500,  2),
  ('Centro-Oeste',   '73700000', '79999999', 2500,  5),
  ('Sudeste',        '01000000', '39999999', 3000,  5),
  ('Sul',            '80000000', '99999999', 3500,  7),
  ('Norte/Nordeste', '40000000', '69999999', 4500, 10)
on conflict do nothing;