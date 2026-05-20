-- 003_commission.sql
-- Provízne polia na leads. Bot ich vyplní pri prechode na status='sold'.
-- Schema je generická — neviaže sa na žiaden konkrétny model výpočtu;
-- pravidlá žijú v src/services/commission.py:compute_commission().

ALTER TABLE public.leads
  ADD COLUMN IF NOT EXISTS commission_amount NUMERIC(10, 2),
  ADD COLUMN IF NOT EXISTS commission_rate NUMERIC(5, 4),
  ADD COLUMN IF NOT EXISTS commission_calculated_at TIMESTAMPTZ;
