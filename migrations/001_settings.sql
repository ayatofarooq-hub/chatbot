BEGIN;

CREATE TABLE IF NOT EXISTS public.admin_users (
    id bigserial PRIMARY KEY,
    username varchar(80) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.admin_sessions (
    id uuid PRIMARY KEY,
    admin_user_id bigint NOT NULL REFERENCES public.admin_users(id) ON DELETE CASCADE,
    token_hash char(64) NOT NULL UNIQUE,
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.model_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    chat_model varchar(160) NOT NULL DEFAULT 'qwen2.5:7b',
    embedding_model varchar(160) NOT NULL DEFAULT 'bge-m3',
    ollama_base_url varchar(255) NOT NULL DEFAULT 'http://127.0.0.1:11434',
    request_timeout integer NOT NULL DEFAULT 300 CHECK (request_timeout BETWEEN 5 AND 1800),
    keep_alive varchar(32) NOT NULL DEFAULT '10m',
    max_answer_tokens integer NOT NULL DEFAULT 400 CHECK (max_answer_tokens BETWEEN 64 AND 8192),
    temperature numeric(4,3) NOT NULL DEFAULT 0 CHECK (temperature BETWEEN 0 AND 2),
    top_p numeric(4,3) NOT NULL DEFAULT 0.9 CHECK (top_p > 0 AND top_p <= 1),
    context_length integer NOT NULL DEFAULT 8192 CHECK (context_length BETWEEN 1024 AND 131072),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.retrieval_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    chunk_size integer NOT NULL DEFAULT 1100 CHECK (chunk_size BETWEEN 200 AND 10000),
    chunk_overlap integer NOT NULL DEFAULT 120 CHECK (chunk_overlap >= 0),
    semantic_weight numeric(4,3) NOT NULL DEFAULT 0.7 CHECK (semantic_weight BETWEEN 0 AND 1),
    keyword_weight numeric(4,3) NOT NULL DEFAULT 0.3 CHECK (keyword_weight BETWEEN 0 AND 1),
    result_count integer NOT NULL DEFAULT 8 CHECK (result_count BETWEEN 1 AND 50),
    hybrid_search boolean NOT NULL DEFAULT true,
    debug_context boolean NOT NULL DEFAULT false,
    ocr_enabled boolean NOT NULL DEFAULT true,
    ocr_language varchar(8) NOT NULL DEFAULT 'ara' CHECK (ocr_language IN ('ara','eng','ara+eng')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (chunk_overlap < chunk_size),
    CHECK (abs((semantic_weight + keyword_weight) - 1) < 0.001)
);

CREATE TABLE IF NOT EXISTS public.authentication_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    login_enabled boolean NOT NULL DEFAULT true,
    remember_login boolean NOT NULL DEFAULT true,
    session_timeout_minutes integer CHECK (session_timeout_minutes IN (15,30,60,240) OR session_timeout_minutes IS NULL),
    password_min_length integer NOT NULL DEFAULT 12 CHECK (password_min_length BETWEEN 8 AND 128),
    require_numbers boolean NOT NULL DEFAULT true,
    require_symbols boolean NOT NULL DEFAULT false,
    require_uppercase boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.appearance_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    language varchar(2) NOT NULL DEFAULT 'ar' CHECK (language IN ('ar','en')),
    theme varchar(8) NOT NULL DEFAULT 'system' CHECK (theme IN ('light','dark','system')),
    primary_color varchar(16) NOT NULL DEFAULT 'green' CHECK (primary_color IN ('green','gold','blue','custom')),
    custom_primary_color varchar(7),
    interface_scale varchar(8) NOT NULL DEFAULT 'medium' CHECK (interface_scale IN ('small','medium','large')),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.upload_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    max_file_size_mb integer NOT NULL DEFAULT 20 CHECK (max_file_size_mb BETWEEN 1 AND 500),
    max_file_count integer NOT NULL DEFAULT 3 CHECK (max_file_count BETWEEN 1 AND 50),
    allow_docx boolean NOT NULL DEFAULT true,
    allow_pdf boolean NOT NULL DEFAULT true,
    allow_txt boolean NOT NULL DEFAULT true,
    ocr_enabled boolean NOT NULL DEFAULT true,
    ocr_language varchar(8) NOT NULL DEFAULT 'ara' CHECK (ocr_language IN ('ara','eng','ara+eng')),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.notification_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    browser_notifications boolean NOT NULL DEFAULT false,
    processing_completed boolean NOT NULL DEFAULT true,
    upload_failed boolean NOT NULL DEFAULT true,
    model_error boolean NOT NULL DEFAULT true,
    index_rebuild_completed boolean NOT NULL DEFAULT true,
    database_backup_completed boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.backup_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    automatic_frequency varchar(8) CHECK (automatic_frequency IN ('daily','weekly','monthly') OR automatic_frequency IS NULL),
    local_destination text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.backup_history (
    id bigserial PRIMARY KEY,
    file_name text NOT NULL,
    status varchar(16) NOT NULL CHECK (status IN ('completed','failed','restored')),
    details text,
    created_by bigint REFERENCES public.admin_users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.document_classifications (
    id bigserial PRIMARY KEY,
    source_value varchar(255) NOT NULL UNIQUE,
    name_ar varchar(255) NOT NULL UNIQUE,
    name_en varchar(255) NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    icon_identifier varchar(64) NOT NULL DEFAULT 'document',
    color varchar(7) NOT NULL DEFAULT '#145a38' CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    enabled boolean NOT NULL DEFAULT true,
    display_order integer NOT NULL DEFAULT 0,
    deleted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.model_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO public.retrieval_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO public.authentication_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO public.appearance_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO public.upload_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO public.notification_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO public.backup_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

INSERT INTO public.document_classifications (source_value, name_ar, name_en, display_order)
SELECT classification, classification, classification, row_number() OVER (ORDER BY classification)
FROM (SELECT DISTINCT classification FROM public.iraqi_laws) values_from_laws
ON CONFLICT DO NOTHING;

COMMIT;
