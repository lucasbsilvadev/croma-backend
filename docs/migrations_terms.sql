-- ============================================================
-- Croma Drip — Migração: terms_versions
-- ============================================================
-- Objetivo: tabela de versões publicadas dos Termos de Uso.
-- Fonte da verdade da versão vigente (LGPD-01).
--
-- Características:
--   - Não destrutiva. Só cria tabela nova e policies.
--   - Leitura pública de versões ativas (GET /terms/current).
--   - Escrita só via service_role (backend / admin).
-- ============================================================

create table if not exists public.terms_versions (
  id uuid primary key default gen_random_uuid(),
  version text not null unique check (char_length(version) between 1 and 64),
  effective_at timestamptz not null default now(),
  document_hash text,
  url text,
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.terms_versions enable row level security;

-- Leitura pública só de versões ativas (endpoint GET /terms/current).
-- Escrita: nenhuma policy → só service_role grava.
drop policy if exists terms_versions_select_active on public.terms_versions;
create policy terms_versions_select_active
  on public.terms_versions
  for select
  using (ativo = true);

-- Seed: versão vigente (data de publicação, formato YYYY-MM-DD — LGPD-01).
insert into public.terms_versions (version, effective_at, ativo)
values ('2026-10-13', now(), true)
on conflict (version) do nothing;

-- Desativa o seed antigo de teste (se existir).
update public.terms_versions
   set ativo = false
 where version = 'v0-template';