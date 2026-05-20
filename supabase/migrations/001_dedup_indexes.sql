-- 001_dedup_indexes.sql
-- Indexy pre dedup query v Database.find_duplicate_leads().
-- Bez týchto by každá nová lead submission robila sequential scan nad celou tabuľkou.
-- Idempotentné — bezpečné re-runnúť.

CREATE INDEX IF NOT EXISTS idx_leads_client_phone ON public.leads(client_phone);
CREATE INDEX IF NOT EXISTS idx_leads_client_email ON public.leads(client_email);
