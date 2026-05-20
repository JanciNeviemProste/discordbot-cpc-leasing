-- ============================================================
-- SYNAPSE DRIVE BOT — Supabase schema
-- Spusti v Supabase SQL Editor (raz, pri prvom setupe)
-- ============================================================

-- Extension pre UUID
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABLE: leads
-- ============================================================
CREATE TABLE IF NOT EXISTS public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Klient (osobné údaje — chránené, prístup len service role)
    client_name TEXT NOT NULL,
    client_phone TEXT NOT NULL,
    client_email TEXT NOT NULL,

    -- Auto
    car_url TEXT,
    car_make TEXT,
    car_model TEXT,
    car_year INTEGER,
    car_price NUMERIC(10, 2),
    car_fuel TEXT,
    car_km INTEGER,
    car_vin TEXT,
    car_raw_description TEXT,   -- ak flipper zadal popis namiesto URL

    -- Atribúcia
    flipper_discord_id TEXT NOT NULL,
    flipper_discord_name TEXT NOT NULL,

    -- Status
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'contacted', 'approved', 'rejected', 'sold')),
    status_updated_at TIMESTAMPTZ,
    status_updated_by TEXT,
    status_note TEXT,

    -- GDPR
    gdpr_consent BOOLEAN NOT NULL DEFAULT FALSE,
    gdpr_consent_at TIMESTAMPTZ,

    -- Discord refs
    discord_message_id TEXT,
    discord_channel_id TEXT,

    -- Provízie (placeholder framework — pravidlá v src/services/commission.py)
    commission_amount NUMERIC(10, 2),
    commission_rate NUMERIC(5, 4),
    commission_calculated_at TIMESTAMPTZ,

    -- WhatsApp
    whatsapp_sent BOOLEAN NOT NULL DEFAULT FALSE,
    whatsapp_sent_at TIMESTAMPTZ,
    whatsapp_message_id TEXT,
    whatsapp_error TEXT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_leads_flipper ON public.leads(flipper_discord_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON public.leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_created ON public.leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_discord_msg ON public.leads(discord_message_id);
CREATE INDEX IF NOT EXISTS idx_leads_client_phone ON public.leads(client_phone);
CREATE INDEX IF NOT EXISTS idx_leads_client_email ON public.leads(client_email);

-- ============================================================
-- TABLE: lead_status_history (audit log)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.lead_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by_discord_id TEXT NOT NULL,
    changed_by_name TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_lead ON public.lead_status_history(lead_id);
CREATE INDEX IF NOT EXISTS idx_history_changed_at ON public.lead_status_history(changed_at DESC);

-- ============================================================
-- TRIGGER: auto-update updated_at on leads
-- ============================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_leads_updated_at ON public.leads;
CREATE TRIGGER trg_leads_updated_at
    BEFORE UPDATE ON public.leads
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- TRIGGER: log status changes automatically
-- ============================================================
CREATE OR REPLACE FUNCTION public.log_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO public.lead_status_history(
            lead_id, old_status, new_status,
            changed_by_discord_id, changed_by_name, note
        ) VALUES (
            NEW.id, OLD.status, NEW.status,
            COALESCE(NEW.status_updated_by, 'system'),
            NEW.status_updated_by,
            NEW.status_note
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_leads_status_history ON public.leads;
CREATE TRIGGER trg_leads_status_history
    AFTER UPDATE ON public.leads
    FOR EACH ROW
    EXECUTE FUNCTION public.log_status_change();

-- ============================================================
-- RLS (Row Level Security)
-- Bot používa service_role key → bypasses RLS.
-- Ak neskôr pridáš web admin, povoľ podľa role.
-- ============================================================
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_status_history ENABLE ROW LEVEL SECURITY;

-- Service role má plný prístup (default behavior, ale explicitne):
DROP POLICY IF EXISTS "service_role_full_access_leads" ON public.leads;
CREATE POLICY "service_role_full_access_leads" ON public.leads
    FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "service_role_full_access_history" ON public.lead_status_history;
CREATE POLICY "service_role_full_access_history" ON public.lead_status_history
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- VIEW: leads_summary (pre budúci web admin / reporting)
-- ============================================================
CREATE OR REPLACE VIEW public.leads_summary AS
SELECT
    l.id,
    l.client_name,
    l.client_phone,
    l.client_email,
    l.car_make || ' ' || COALESCE(l.car_model, '') AS car_full,
    l.car_year,
    l.car_price,
    l.flipper_discord_name,
    l.status,
    l.created_at,
    l.status_updated_at,
    (SELECT COUNT(*) FROM public.lead_status_history h WHERE h.lead_id = l.id) AS status_changes
FROM public.leads l
ORDER BY l.created_at DESC;

-- ============================================================
-- HOTOVO. Skontroluj: SELECT * FROM leads_summary LIMIT 1;
-- ============================================================
