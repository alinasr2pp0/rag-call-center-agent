# RAG Call Center Agent (Arabic)

Merged project: customer sends a problem as text -> RAG agent answers from the
KB -> 3 minutes later, an outbound call confirms whether it was actually
resolved -> if not, the agent retries with broader KB retrieval, then a Tavily
web search -> after 3 total attempts with no resolution, the call transfers to
a human agent. If the customer confirms resolution at any point, the ticket
closes.

Telephony runs on **Vonage Voice API** (NCCO-based call control).

## Run

Database defaults to **SQLite** — zero install, no service to start, just a
local file (`call_center_rag.db`, created automatically). Swap to Postgres in
`.env` if you want a more production-like setup (see the comment next to
`DATABASE_URL` in `.env.example`).

**Windows shortcut:** double-click `start_project.bat` — it launches `ngrok`,
writes the fresh ngrok URL into `PUBLIC_BASE_URL` in `.env` automatically,
starts PostgreSQL *only if* you've switched to it (safely skipped otherwise),
then starts the server. Requires `ngrok` installed and on your PATH, and a
`.env` already filled in (see below). Otherwise, run manually:

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in the keys below
python seed_kb.py      # loads kb_articles_sample.json into your DB + Pinecone
uvicorn app.main:app --reload
```

Pinecone index must exist already, with a dimension matching your Voyage
model's output size, before running `seed_kb.py`.

`PUBLIC_BASE_URL` must be a public HTTPS URL for Vonage to reach the
`answer`/`event`/`gather` webhooks (use `ngrok http 8000` locally).

## Flow / attempt logic

| Attempt | Trigger | Strategy |
|---|---|---|
| 1 | first text message | narrow KB retrieval (top_k=5, min_score=0.75) |
| 2 | customer says "still not resolved" on the call | broad KB retrieval (top_k=10, min_score=0.55) |
| 3 | still unresolved | Tavily web search, LLM synthesizes an answer |
| — | still unresolved after attempt 3 | call transfers live to a human agent |

Confirmed business rules (already set in `.env.example`):
- `FOLLOWUP_CALL_DELAY_SECONDS=180` (3 minutes)
- `MAX_RESOLUTION_ATTEMPTS=3`

## Telephony: Vonage Voice API

The call itself is driven by NCCO (Vonage's JSON call-control format) rather
than Twilio's TwiML — Vonage's own Arabic ASR and TTS voices handle the
audio, same as the previous Twilio-based flow did (no custom STT/TTS service
needed on our side).

**Setup:**
1. Sign up at [dashboard.nexmo.com](https://dashboard.nexmo.com) — free
   trial, no card required, ~$2 credit.
2. Create a **Voice-enabled Application** (Applications > Create a new
   application). Vonage generates a private key file — download it once, you
   can't re-download it later.
3. Fill `.env`: `VONAGE_APPLICATION_ID` (shown on the application page),
   `VONAGE_PRIVATE_KEY` (the full key file content, newlines escaped as
   `\n` — see the comment in `.env.example`), and `VONAGE_FROM_NUMBER`
   (a Vonage virtual number, **digits only, no `+`**).
4. During trial, verify your own number (and the agent's number, if you want
   to test live transfer) from the dashboard — trial calls only reach
   verified numbers.
5. `POST /tickets/message` with your verified number as `customer_phone`,
   wait 3 minutes, answer the call.

**Trial vs. Twilio, a real difference:** Twilio's trial flatly blocks the
`<Stream>` and `<Dial><Number>` actions outright. Vonage's trial restriction
is destination-based instead (calls only reach verified numbers) — the
`connect` action used for escalation (`telephony.build_transfer_ncco`) is not
itself blocked, so a real live transfer works in trial as long as
`HUMAN_AGENT_TRANSFER_NUMBER` is also verified. (This is based on Vonage's
documented trial restrictions; verify against your own account before
relying on it.)

## Frontend (demo)

A minimal Arabic chat widget lives in `static/index.html` and is served at
`/` by the FastAPI app itself (no separate server needed) — it posts
directly to `/tickets/message` and shows the answer, its source (KB/web
search), confidence, and a countdown note for the follow-up call. It's a
demo for testing the text-resolution flow only; it does not show call
outcomes (those only exist in the DB/transcript for now).

## Admin & Access Control

Four roles, matching the access diagram: **superadmin > admin > agent**
(staff, password login) and **customer** (phone + SMS OTP login, no
password, scoped to their own data only).

- **Staff login**: `POST /auth/login` issues a JWT with role `superadmin`,
  `admin`, or `agent`. The very first account is auto-created as
  **superadmin** on first startup (`ADMIN_DEFAULT_USERNAME`/
  `ADMIN_DEFAULT_PASSWORD` in `.env`, defaults to `admin` / `changeme123`)
  — **change the password immediately in production**.
- **Staff roles**:
  - `agent` — read-only: view tickets, calls, escalations, KB.
  - `admin` — everything an agent can do, plus create/edit/delete KB articles.
  - `superadmin` — everything an admin can do, plus manage staff accounts
    themselves via `/staff` (create, change role, delete).
- **Customer login** (`POST /customer-auth/request-otp` then
  `/customer-auth/verify-otp`): a customer verifies their phone number with
  an SMS code (Vonage Verify — enable the "Verify" capability on your Vonage
  Application, not just "Voice") and gets a JWT scoped only to their own
  phone number. `GET /customer-auth/my/tickets` returns just their tickets —
  a customer token can never reach `/admin/*` or `/staff/*` (enforced by
  `require_staff`/`require_admin`/`require_superadmin` in `app/services/auth.py`).
- **Admin dashboard** (`static/admin.html`, served at `/admin.html`): stats,
  tickets table with full detail, and full KB management. Staff-account
  management and the customer portal are API-only for now (no dedicated UI
  screens yet — happy to build those next if useful).
- Like the customer widget, `admin.html` falls back to mock data automatically
  if it can't reach a real backend, so you can preview the whole dashboard
  before wiring up your database/Pinecone.

## Endpoints

- `POST /tickets/message` — `{customer_phone, customer_name?, problem_text}` →
  first RAG answer + schedules the confirmation call
- `GET /webhooks/answer/{call_id}` — Vonage fetches the NCCO here on answer (internal)
- `POST /webhooks/gather/{call_id}` — Vonage posts recognized speech here; the
  confirmation-call retry loop lives here (internal)
- `POST /webhooks/event/{call_id}` — Vonage call-status events (internal)
- `POST /auth/login` — staff login (superadmin/admin/agent)
- `GET/POST/PUT/DELETE /staff` — manage staff accounts (superadmin only)
- `POST /customer-auth/request-otp`, `POST /customer-auth/verify-otp` —
  customer phone login
- `GET /customer-auth/my/tickets` — a logged-in customer's own tickets

## API keys you need to supply

`.env.example` is filled in with working local-dev defaults for everything
*except* the actual API keys — copy it to `.env` and drop your keys in.
No free alternative exists for these:

- **Voyage AI** — `VOYAGE_API_KEY`
- **Pinecone** — `PINECONE_API_KEY` (+ create the index first, see above)
- **OpenRouter** — `OPENROUTER_API_KEY`
- **Tavily** — `TAVILY_API_KEY` (has a free tier)
- **Vonage** — `VONAGE_APPLICATION_ID`, `VONAGE_PRIVATE_KEY`, `VONAGE_FROM_NUMBER`
  (free trial available, see the Telephony section above)

## What's stubbed / needs your attention before production

- `HUMAN_AGENT_TRANSFER_NUMBER` needs a real line/queue (and, during trial,
  a verified Vonage test number).
- `llm.generate_kb_answer`'s confidence score is self-reported by the LLM —
  worth validating against real usage before trusting it fully; consider
  cross-checking with the retrieval `score` from Pinecone too.
- Change `JWT_SECRET` and `ADMIN_DEFAULT_PASSWORD` before any real deployment.
  Setting `ENVIRONMENT=production` in `.env` now makes the app refuse to
  start if either is still the placeholder value.
- No real-time low-latency audio streaming flow exists on the Vonage side
  yet (the old Twilio `<Stream>` websocket flow was removed since it was
  Twilio-specific end to end). Vonage does support a WebSocket NCCO
  `connect` type for this; it would be a separate addition if you want
  lower-latency audio with your own STT/TTS instead of Vonage's built-in ASR/TTS.

### Resolved in earlier review passes

- **Call scheduling survives a restart.** `scheduler.py` writes a `Call` row
  with `status='scheduled'` to Postgres instead of holding the delay in
  memory; a background poller (`run_call_dispatcher`, started at app
  startup) places whatever is due. No Celery/Redis needed.
- **Retry on no-answer/busy/failed**, up to `MAX_CALL_RETRIES` times
  (`CALL_RETRY_DELAY_SECONDS` apart), then escalates with reason
  `call_unreachable`.
- **CORS is configurable** via `ALLOWED_ORIGINS` (comma-separated).
- **Resolution traceability**: `Resolution.kb_article_id` and
  `web_search_log_id` are populated correctly; `Ticket.category` is inferred
  from the resolving KB article.
- **Routing bug fixed**: the static file mount at `/` is registered last so
  it can't shadow `/health` or any other route.
- **Escalation loop fixed**: a single empty-KB-match no longer short-circuits
  straight to escalation — the resolution agent now advances through
  narrow KB → broad KB → web search within one call before giving up.
- **XML/JSON injection guard**: outbound text is properly escaped before
  being embedded in call-control payloads.
