BEGIN;

ALTER TABLE public.authentication_settings
    DROP COLUMN IF EXISTS guest_access;

ALTER TABLE public.admin_users
    ADD COLUMN IF NOT EXISTS display_name varchar(120),
    ADD COLUMN IF NOT EXISTS email varchar(255),
    ADD COLUMN IF NOT EXISTS role varchar(32) NOT NULL DEFAULT 'super_admin',
    ADD COLUMN IF NOT EXISTS password_changed_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS last_login_at timestamptz,
    ADD COLUMN IF NOT EXISTS created_by bigint REFERENCES public.admin_users(id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'admin_users_role_check'
          AND conrelid = 'public.admin_users'::regclass
    ) THEN
        ALTER TABLE public.admin_users
            ADD CONSTRAINT admin_users_role_check
            CHECK (role IN ('super_admin','admin','viewer'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS admin_users_email_unique
    ON public.admin_users (lower(email))
    WHERE email IS NOT NULL AND email <> '';

CREATE TABLE IF NOT EXISTS public.admin_audit_log (
    id bigserial PRIMARY KEY,
    actor_user_id bigint REFERENCES public.admin_users(id) ON DELETE SET NULL,
    actor_username varchar(80),
    action varchar(80) NOT NULL,
    target_type varchar(80),
    target_id text,
    ip_address inet,
    user_agent text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS admin_audit_log_created_at_idx
    ON public.admin_audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS admin_audit_log_actor_idx
    ON public.admin_audit_log (actor_user_id, created_at DESC);

UPDATE public.authentication_settings
SET login_enabled = true,
    updated_at = now()
WHERE id = 1;

COMMIT;
