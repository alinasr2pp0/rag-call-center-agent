# RAG Call Center Agent (Arabic)

Arabic AI Call Center Agent that combines **RAG, LLMs, Web Search, Voice Calls, and Human Escalation**.

The customer sends a problem as text. The system generates an answer from the Knowledge Base, then calls the customer after 3 minutes to confirm whether the problem was resolved.

If it is not resolved, the system progressively escalates:

```text
Attempt 1 → Narrow KB Retrieval
Attempt 2 → Broad KB Retrieval
Attempt 3 → Tavily Web Search
Final     → Human Agent
```

Telephony is handled by **Vonage Voice API using NCCO**.

---

## 1. Architecture

```text
Customer
   │
   ▼
FastAPI Router
   │
   ▼
Resolution Agent
   │
   ├── Attempt 1 → Pinecone + LLM
   │
   ├── Attempt 2 → Broader Pinecone + LLM
   │
   └── Attempt 3 → Tavily + LLM
   │
   ▼
Schedule Follow-up
   │
   ▼
Vonage Voice Call
   │
   ├── Resolved → Close Ticket
   │
   └── Unresolved → Next Attempt
                       │
                       ▼
                 Human Agent
```

### Main responsibility separation

| Component        | Responsibility                         |
| ---------------- | -------------------------------------- |
| RAG              | Retrieval + knowledge-based generation |
| LLM              | Answer generation + classification     |
| Resolution Agent | Decision making + workflow             |
| Scheduler        | Delayed call scheduling                |
| Telephony        | Vonage calls + NCCO                    |
| Verify           | Customer OTP                           |
| Routers          | API/Webhook entry points               |
| Database         | Persistent application state           |
| Auth             | JWT + permissions                      |

---

# 2. Project Structure

```text
rag-call-center-agent/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── db.py
│   │
│   ├── services/
│   │   ├── auth.py
│   │   │
│   │   ├── rag/
│   │   │   ├── embeddings.py
│   │   │   ├── vectorstore.py
│   │   │   ├── llm.py
│   │   │   └── web_search.py
│   │   │
│   │   └── agent/
│   │       ├── resolution_agent.py
│   │       ├── telephony.py
│   │       ├── verify.py
│   │       └── scheduler.py
│   │
│   └── routers/
│       ├── chat.py
│       ├── webhooks.py
│       ├── auth.py
│       ├── staff.py
│       ├── customer_auth.py
│       └── admin.py
│
├── static/
│   ├── index.html
│   └── admin.html
│
├── docs/
│   └── evaluation_and_metrics.md
│
├── README.md
├── requirements.txt
├── .env.example
├── schema.sql
├── seed_kb.py
├── kb_articles_sample.json
└── start_project.bat
```

---

# 3. Services

## RAG

### `embeddings.py`

Generates embeddings using **Voyage AI**.

### `vectorstore.py`

Handles **Pinecone** indexing and retrieval.

### `llm.py`

Handles **OpenRouter / LLM** generation and classification.

### `web_search.py`

Handles **Tavily** web search for the third resolution attempt.

---

## Agent

### `resolution_agent.py`

The central workflow controller.

```text
Attempt 1
   ↓
Narrow KB
top_k=5
min_score=0.75

Attempt 2
   ↓
Broad KB
top_k=10
min_score=0.55

Attempt 3
   ↓
Tavily Web Search

Still unresolved
   ↓
Human Agent
```

### `telephony.py`

Handles **Vonage Voice API**:

* Outbound calls
* NCCO
* Speech/Gather
* Call transfer
* Call status

### `scheduler.py`

Schedules the follow-up call.

Default:

```env
FOLLOWUP_CALL_DELAY_SECONDS=180
```

The scheduled call is stored in the database, so it survives application restarts.

### `verify.py`

Handles customer phone verification using **Vonage Verify + SMS OTP**.

---

# 4. Authentication

The system has:

```text
superadmin
    ↓
admin
    ↓
agent

customer
```

### Agent

Read-only access to tickets, calls, resolutions, and KB.

### Admin

Agent permissions + KB management.

### Superadmin

Admin permissions + staff management.

### Customer

Phone + OTP authentication and access only to their own tickets.

JWT and authorization logic are implemented in:

```text
app/services/auth.py
```

---

# 5. Database

Default:

```env
DATABASE_URL=sqlite:///./call_center_rag.db
```

SQLite requires no separate service.

For production-like environments, PostgreSQL can be used instead.

Main entities include:

```text
User
Ticket
Call
Resolution
KBArticle
WebSearchLog
```

---

# 6. Required API Services

The project requires:

| Service       | Purpose                             |
| ------------- | ----------------------------------- |
| Voyage AI     | Embeddings                          |
| Pinecone      | Vector Database                     |
| OpenRouter    | LLM                                 |
| Tavily        | Web Search                          |
| Vonage Voice  | Calls                               |
| Vonage Verify | Customer OTP                        |
| ngrok         | Public HTTPS URL for local webhooks |

---

# 7. Environment Configuration

Create `.env` from `.env.example`.

Example:

```env
DATABASE_URL=sqlite:///./call_center_rag.db

VOYAGE_API_KEY=
PINECONE_API_KEY=
OPENROUTER_API_KEY=
TAVILY_API_KEY=

VONAGE_APPLICATION_ID=
VONAGE_PRIVATE_KEY=
VONAGE_FROM_NUMBER=
HUMAN_AGENT_TRANSFER_NUMBER=

JWT_SECRET=

ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=changeme123

FOLLOWUP_CALL_DELAY_SECONDS=180
MAX_RESOLUTION_ATTEMPTS=3

PUBLIC_BASE_URL=
ALLOWED_ORIGINS=http://localhost:8000

ENVIRONMENT=development
```

Never commit the real `.env` file to Git.

---

# 8. Setup

## Clone the project

```bash
git clone <YOUR_REPOSITORY_URL>
cd rag-call-center-agent
```

---

## Create Virtual Environment

### Windows

```bash
python -m venv .venv
```

Activate:

```powershell
.venv\Scripts\Activate.ps1
```

### Linux / Ubuntu

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

# 9. Run in VS Code

Open the project:

```bash
code .
```

In VS Code:

```text
Ctrl + Shift + P
        ↓
Python: Select Interpreter
        ↓
.venv
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env`:

### Windows

```powershell
Copy-Item .env.example .env
```

### Linux

```bash
cp .env.example .env
```

Then add the required API keys.

---

# 10. Setup Pinecone

Create the Pinecone index first.

The index dimension must match the selected Voyage embedding model.

Then run:

```bash
python seed_kb.py
```

This loads:

```text
kb_articles_sample.json
        ↓
Voyage Embeddings
        ↓
Pinecone
```

---

# 11. Start FastAPI

From the VS Code terminal:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 12. Enable Vonage Webhooks Locally

Vonage needs a public HTTPS URL.

Open another VS Code terminal:

```bash
ngrok http 8000
```

Copy the HTTPS URL:

```text
https://xxxx.ngrok-free.app
```

Set:

```env
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
```

Vonage can then reach:

```text
/webhooks/answer/{call_id}
/webhooks/gather/{call_id}
/webhooks/event/{call_id}
```

---

# 13. Recommended VS Code Terminals

```text
Terminal 1
──────────
uvicorn app.main:app --reload

Terminal 2
──────────
ngrok http 8000

Terminal 3
──────────
python seed_kb.py
```

For debugging, use VS Code **Run & Debug** and place breakpoints inside:

```text
resolution_agent.py
vectorstore.py
llm.py
telephony.py
scheduler.py
webhooks.py
```

---

# 14. Main API Endpoints

### Customer

```http
POST /tickets/message
```

Creates a ticket and performs the first RAG attempt.

### Vonage

```http
GET  /webhooks/answer/{call_id}
POST /webhooks/gather/{call_id}
POST /webhooks/event/{call_id}
```

### Staff

```http
POST /auth/login

GET    /staff
POST   /staff
PUT    /staff/{id}
DELETE /staff/{id}
```

### Customer Authentication

```http
POST /customer-auth/request-otp
POST /customer-auth/verify-otp
GET  /customer-auth/my/tickets
```

---

# 15. Complete Resolution Flow

```text
Customer sends problem
        │
        ▼
Create Ticket
        │
        ▼
Attempt 1
Narrow KB Retrieval
        │
        ▼
LLM Answer
        │
        ▼
Schedule Call
        │
        ▼
Customer receives call
        │
        ├── Resolved ──→ Close Ticket
        │
        └── Not Resolved
                  │
                  ▼
              Attempt 2
              Broad KB
                  │
                  ▼
              Still unresolved
                  │
                  ▼
              Attempt 3
              Tavily Search
                  │
             ┌────┴────┐
             ▼         ▼
          Resolved   Failed
             │         │
             ▼         ▼
        Close Ticket  Human Agent
```

---

# 16. Evaluation

RAG and Agent should be evaluated separately.

### RAG

```text
Recall@K
Precision@K
MRR
Context Relevance
Faithfulness
Answer Relevance
```

### Agent

```text
Resolution Rate
First-Attempt Resolution Rate
Escalation Rate
Call Success Rate
Retry Rate
Average Attempts
Average Resolution Time
```

See:

```text
docs/evaluation_and_metrics.md
```

---

# 17. Production Notes

Before production:

* Change `JWT_SECRET`.
* Change `ADMIN_DEFAULT_PASSWORD`.
* Never commit `.env`.
* Configure a real `HUMAN_AGENT_TRANSFER_NUMBER`.
* Use PostgreSQL for production.
* Monitor retrieval quality.
* Validate LLM confidence instead of blindly trusting it.
* Keep the Knowledge Base synchronized with the vector database.
* Log ticket, attempt, retrieval, call, and resolution information for traceability.
* Configure proper CORS and HTTPS.

---

# 18. One-Click Windows Startup

After configuring the project:

```text
start_project.bat
```

can start the local development environment, including ngrok and FastAPI.

For debugging and development, running the services manually from separate VS Code terminals is recommended.

---

# 19. Core Architecture Principle

```text
Router
  ↓
Agent
  ↓
┌───────────────┬──────────────┐
│               │              │
RAG          Scheduler      Telephony
│               │              │
├─ Embedding    │              └─ Vonage
├─ Pinecone     │
├─ LLM          └─ Delayed Calls
└─ Tavily
```

### In one sentence:

> **RAG provides the knowledge, LLM generates the response, the Agent controls the workflow, the Scheduler controls timing, Vonage handles communication, and the Database preserves the state.**
