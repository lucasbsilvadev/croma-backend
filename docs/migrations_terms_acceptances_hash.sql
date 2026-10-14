-- ============================================================
-- Croma Drip — Migração: document_hash em terms_acceptances
-- ============================================================
-- Objetivo: adicionar prova criptográfica do texto aceito.
-- Referência: LGPD-01.
--
-- Características:
--   - Não destrutiva. Só adiciona coluna nullable.
--   - Aceites antigos ficam com NULL (não há como recuperar
--     o texto aceito antes desta decisão).
--   - Não altera RLS, não altera policies.
-- ============================================================

alter table public.terms_acceptances
  add column if not exists document_hash text;

-- Índice opcional: busca por document_hash (auditoria futura).
create index if not exists terms_acceptances_document_hash_idx
  on public.terms_acceptances(document_hash)
  where document_hash is not null;