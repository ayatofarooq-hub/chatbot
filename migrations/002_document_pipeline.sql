BEGIN;

CREATE TABLE IF NOT EXISTS public.fine_tuning_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    learning_mode varchar(16) NOT NULL DEFAULT 'manual'
        CHECK (learning_mode IN ('manual','automatic')),
    auto_approval_threshold numeric(4,3) NOT NULL DEFAULT 0.85
        CHECK (auto_approval_threshold BETWEEN 0 AND 1),
    validation_threshold numeric(4,3) NOT NULL DEFAULT 0.80
        CHECK (validation_threshold BETWEEN 0 AND 1),
    scheduled_start_time time NOT NULL DEFAULT '02:00',
    system_signed_in boolean NOT NULL DEFAULT true,
    live_model_run_id uuid,
    live_model_id text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.documents (
    id bigserial PRIMARY KEY,
    file_path text NOT NULL,
    uploaded_by text NOT NULL,
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    status varchar(32) NOT NULL DEFAULT 'uploaded'
        CHECK (status IN (
            'uploaded','classified','unclassified','approved','used_in_training'
        )),
    category varchar(255),
    classification_confidence numeric(5,4),
    classified_by text,
    classified_at timestamptz,
    used_in_run_id uuid,
    manual_override boolean NOT NULL DEFAULT false,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        status NOT IN ('classified','approved','used_in_training')
        OR nullif(trim(category), '') IS NOT NULL
    ),
    CHECK (classification_confidence IS NULL OR classification_confidence BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS documents_review_queue_idx
    ON public.documents (status, uploaded_at)
    WHERE status IN ('uploaded','unclassified');

CREATE INDEX IF NOT EXISTS documents_training_eligible_idx
    ON public.documents (status, used_in_run_id)
    WHERE status = 'approved' AND used_in_run_id IS NULL;

CREATE TABLE IF NOT EXISTS public.document_status_audit (
    id bigserial PRIMARY KEY,
    document_id bigint NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    from_status varchar(32),
    to_status varchar(32) NOT NULL,
    actor text NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fine_tuning_runs (
    id uuid PRIMARY KEY,
    model_id text NOT NULL,
    status varchar(24) NOT NULL
        CHECK (status IN ('running','failed_validation','completed','discarded')),
    eligible_count integer NOT NULL DEFAULT 0 CHECK (eligible_count >= 0),
    validation_score numeric(5,4),
    details text,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS public.document_pipeline_events (
    id bigserial PRIMARY KEY,
    event_type varchar(48) NOT NULL,
    actor text NOT NULL DEFAULT 'system',
    reason text NOT NULL,
    run_id uuid,
    document_count integer NOT NULL DEFAULT 0 CHECK (document_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.fine_tuning_settings (id) VALUES (1)
ON CONFLICT DO NOTHING;

COMMIT;
