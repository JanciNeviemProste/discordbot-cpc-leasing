-- 002_admin_read_access.sql
-- RLS policy pre web admin (synapse-drive-admin Next.js projekt).
--
-- Bot používa service_role key a obíde RLS. Admin používa Supabase Auth +
-- anon key; bez tejto policy by autentifikovaný admin nevidel nič.
--
-- Bezpečnosť: kto sa môže prihlásiť do admin-u kontroluje ALLOWED_EMAILS
-- env var v Next.js middleware + auth/callback route. Tu len povolíme
-- akéhokoľvek autentifikovaného usera čítať — autorizáciu rieši aplikácia.

DROP POLICY IF EXISTS "authenticated_read_leads" ON public.leads;
CREATE POLICY "authenticated_read_leads" ON public.leads
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "authenticated_read_history" ON public.lead_status_history;
CREATE POLICY "authenticated_read_history" ON public.lead_status_history
    FOR SELECT
    TO authenticated
    USING (true);
