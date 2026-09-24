-- =====================================================================
-- Data model for the merged RAG + Agent + Voice Call Center project
-- Covers: text-first RAG resolution -> confirmation call -> deeper
-- retrieval / web search -> human escalation, with full traceability.
-- =====================================================================

CREATE TABLE customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           VARCHAR NOT NULL,
    name            VARCHAR,
    created_at      TIMESTAMP DEFAULT now()
);

-- One row per customer problem, from first message to final closure.
CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    status          VARCHAR NOT NULL DEFAULT 'open',
        -- open | resolved_by_rag | awaiting_confirmation |
        -- resolved_confirmed | reopened | escalated | closed
    category        VARCHAR,           -- best-matching KB category, for reporting
    opened_at       TIMESTAMP DEFAULT now(),
    closed_at       TIMESTAMP,
    resolution_attempts INTEGER DEFAULT 0   -- increments each time a fix is tried
);

-- The knowledge base itself.
CREATE TABLE kb_articles (
    id                  VARCHAR PRIMARY KEY,   -- e.g. "KB-0001"
    category            VARCHAR NOT NULL,
    subcategory         VARCHAR,
    title               VARCHAR NOT NULL,
    problem_variants    JSONB NOT NULL,   -- list[str], embedded for retrieval
    solution_text       TEXT NOT NULL,
    solution_steps      JSONB,            -- list[str]
    escalate_if         JSONB,            -- list[str] — conditions that mean this article alone won't suffice
    tags                JSONB,
    source              VARCHAR,
    last_verified_at    DATE
);

-- Every text message exchanged with the customer (first contact channel).
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID NOT NULL REFERENCES tickets(id),
    sender          VARCHAR NOT NULL,   -- 'customer' | 'agent'
    content         TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT now()
);

-- Every attempt to resolve the ticket, from any source, fully traceable.
CREATE TABLE resolutions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id           UUID NOT NULL REFERENCES tickets(id),
    source              VARCHAR NOT NULL,   -- 'kb' | 'web_search' | 'human'
    kb_article_id       VARCHAR REFERENCES kb_articles(id),   -- set when source = 'kb'
    web_search_log_id   UUID,                                  -- set when source = 'web_search'
    answer_text         TEXT NOT NULL,
    confidence_score    FLOAT,              -- LLM's self-reported confidence, 0-1
    accepted_by_customer BOOLEAN,           -- null until confirmed on the follow-up call
    created_at          TIMESTAMP DEFAULT now()
);

-- Outbound confirmation calls (and any deeper-troubleshooting calls that follow).
CREATE TABLE calls (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id           UUID NOT NULL REFERENCES tickets(id),
    call_type           VARCHAR NOT NULL DEFAULT 'confirmation',
        -- confirmation | troubleshooting | escalation_handoff
    status              VARCHAR DEFAULT 'scheduled',   -- scheduled|in_progress|completed|failed
    outcome             VARCHAR,    -- resolved_confirmed | still_unresolved | transferred_to_agent
    provider_call_id    VARCHAR,  -- Vonage call UUID
    transcript          TEXT,
    scheduled_at        TIMESTAMP,
    started_at          TIMESTAMP,
    ended_at            TIMESTAMP,
    duration_seconds    INTEGER,
    retry_count         INTEGER DEFAULT 0,  -- how many prior no-answer/busy/failed attempts led to this call
    dialog_state        VARCHAR DEFAULT 'awaiting_confirmation'  -- trial-mode Gather loop state
);

-- Web-search fallback results, used when KB retrieval isn't enough.
CREATE TABLE web_search_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID NOT NULL REFERENCES tickets(id),
    query           TEXT NOT NULL,
    source_url      VARCHAR,
    snippet         TEXT,
    used_in_resolution BOOLEAN DEFAULT false,
    created_at      TIMESTAMP DEFAULT now()
);

-- Every hand-off to a human agent, with the reason, for QA and staffing analysis.
CREATE TABLE escalations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID NOT NULL REFERENCES tickets(id),
    call_id         UUID REFERENCES calls(id),   -- set if escalation happened mid-call
    reason          VARCHAR NOT NULL,
        -- kb_no_match | web_search_no_match | max_attempts_reached | customer_requested
    escalated_at    TIMESTAMP DEFAULT now(),
    assigned_agent  VARCHAR
);

-- Staff accounts for the admin dashboard / KB management. Role hierarchy:
-- superadmin (manages staff accounts) > admin (manages KB, full data access)
-- > agent (read-only on tickets/KB). Customers do NOT get a row here — see
-- the customer-auth note below.
CREATE TABLE staff_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR UNIQUE NOT NULL,
    password_hash   VARCHAR NOT NULL,
    role            VARCHAR NOT NULL DEFAULT 'agent',  -- superadmin | admin | agent
    created_at      TIMESTAMP DEFAULT now()
);

-- =====================================================================
-- Indexes worth adding once volume grows
-- =====================================================================
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_messages_ticket ON messages(ticket_id);
CREATE INDEX idx_resolutions_ticket ON resolutions(ticket_id);
CREATE INDEX idx_calls_ticket ON calls(ticket_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_staff_users_role ON staff_users(role);

-- =====================================================================
-- Note on customer authentication
-- =====================================================================
-- Customers don't get a persistent login row: they authenticate via a
-- one-time SMS code (Vonage Verify) tied to their phone number, which
-- issues a short-lived JWT scoped to that phone's own tickets. See
-- app/routers/customer_auth.py and app/services/verify.py.
