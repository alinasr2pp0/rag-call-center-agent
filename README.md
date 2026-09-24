# RAG Call Center Agent (Arabic)

An Arabic AI Call Center Agent that combines **RAG, LLMs, Web Search, Voice Calls, and Human Escalation**.

The customer sends a problem as text. The system generates an answer from the Knowledge Base, then calls the customer after **3 minutes** to verify whether the issue was resolved.

If the issue remains unresolved, the system progressively escalates:

```text
Attempt 1 → Narrow KB Retrieval
Attempt 2 → Broad KB Retrieval
Attempt 3 → Tavily Web Search
Final     → Human Agent
```

Telephony is handled by **Vonage Voice API using NCCO**.

---

## Architecture

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
   ├── Attempt 2 → Broad Pinecone + LLM
   └── Attempt 3 → Tavily + LLM
   │
   ▼
Schedule Follow-up
   │
   ▼
Vonage Voice Call
   │
   ├── Resolved   → Close Ticket
   └── Unresolved → Next Attempt
                         │
                         ▼
                   Human Agent
```

### Responsibility Separation

| Component            | Responsibility                             |
| -------------------- | ------------------------------------------ |
| **RAG**              | Retrieval and knowledge-based generation   |
| **LLM**              | Answer generation and classification       |
| **Resolution Agent** | Decision making and workflow orchestration |
| **Scheduler**        | Delayed call scheduling                    |
| **Telephony**        | Vonage calls and NCCO                      |
| **Verify**           | Customer OTP verification                  |
| **Routers**          | API and webhook entry points               |
| **Database**         | Persistent application state               |
| **Auth**             | JWT authentication and permissions         |

---

## Project Structure

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

## Services

### RAG Services

**`embeddings.py`**
Generates embeddings using Voyage AI.

**`vectorstore.py`**
Handles Pinecone indexing and retrieval.

**`llm.py`**
Handles OpenRouter/LLM generation and classification.

**`web_search.py`**
Handles Tavily web search for the final resolution attempt.

### Agent Services

**`resolution_agent.py`**
Central workflow controller.

```text
Attempt 1 → top_k=5,  min_score=0.75
Attempt 2 → top_k=10, min_score=0.55
Attempt 3 → Tavily Web Search
Final     → Human Agent
```

**`telephony.py`**
Handles Vonage Voice API, outbound calls, NCCO, speech/gather, transfers, and call status.

**`scheduler.py`**
Schedules follow-up calls and persists scheduled jobs in the database.

```env
FOLLOWUP_CALL_DELAY_SECONDS=180
```

**`verify.py`**
Handles customer phone verification using Vonage Verify + SMS OTP.

---

## Authentication

The system supports four roles:

```text
superadmin
    ↓
admin
    ↓
agent

customer
```

* **Agent** — Read-only access to tickets, calls, resolutions, and KB.
* **Admin** — Agent permissions + Knowledge Base management.
* **Superadmin** — Admin permissions + staff management.
* **Customer** — Phone/OTP authentication and access to their own tickets.

Authentication and authorization are implemented in:

```text
app/services/auth.py
```

---

## Tech Stack

| Service                 | Purpose                         |
| ----------------------- | ------------------------------- |
| **FastAPI**             | API and webhooks                |
| **Voyage AI**           | Embeddings                      |
| **Pinecone**            | Vector Database                 |
| **OpenRouter**          | LLM                             |
| **Tavily**              | Web Search                      |
| **Vonage Voice**        | Voice Calls                     |
| **Vonage Verify**       | Customer OTP                    |
| **SQLite / PostgreSQL** | Database                        |
| **ngrok**               | Public HTTPS for local webhooks |

> Never commit the real `.env` file.

---

## Setup

### 1. Clone

```bash
git clone <YOUR_REPOSITORY_URL>
cd rag-call-center-agent
```

### 2. Create Virtual Environment

**Windows**

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / Ubuntu**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

**Windows**

```powershell
Copy-Item .env.example .env
```

**Linux**

```bash
cp .env.example .env
```

Add the required API keys and configuration.

### 5. Setup Pinecone

Create a Pinecone index whose dimension matches the selected Voyage embedding model.

Then seed the Knowledge Base:

```bash
python seed_kb.py
```

### 6. Start the Application

```bash
uvicorn app.main:app --reload
```

Application:

```text
http://127.0.0.1:8000
```

API Docs:

```text
http://127.0.0.1:8000/docs
```

---

## Local Vonage Webhooks

Run ngrok:

```bash
ngrok http 8000
```

Then configure:

```env
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
```

Vonage webhooks:

```http
GET  /webhooks/answer/{call_id}
POST /webhooks/gather/{call_id}
POST /webhooks/event/{call_id}
```

---

## Main Endpoints

### Customer

```http
POST /tickets/message
```

Creates a ticket and starts the resolution workflow.

### Authentication

```http
POST /auth/login

POST /customer-auth/request-otp
POST /customer-auth/verify-otp
GET  /customer-auth/my/tickets
```

### Staff

```http
GET    /staff
POST   /staff
PUT    /staff/{id}
DELETE /staff/{id}
```

---

## Resolution Flow

```text
Customer Problem
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
Schedule Follow-up
       │
       ▼
Vonage Call
       │
       ├── Resolved ──→ Close Ticket
       │
       └── Unresolved
               │
               ▼
           Attempt 2
           Broad KB
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

## Evaluation

### RAG Metrics

```text
Recall@K
Precision@K
MRR
Context Relevance
Faithfulness
Answer Relevance
```

### Agent Metrics

```text
Resolution Rate
First-Attempt Resolution Rate
Escalation Rate
Call Success Rate
Retry Rate
Average Attempts
Average Resolution Time
```

Detailed evaluation:

```text
docs/evaluation_and_metrics.md
```

---

## VS Code Development

Recommended terminals:

```text
Terminal 1
uvicorn app.main:app --reload

Terminal 2
ngrok http 8000

Terminal 3
python seed_kb.py
```

For debugging, use breakpoints in:

```text
resolution_agent.py
vectorstore.py
llm.py
telephony.py
scheduler.py
webhooks.py
```

---

## Production Notes

Before production:

* Change `JWT_SECRET`.
* Change `ADMIN_DEFAULT_PASSWORD`.
* Never commit `.env`.
* Configure a real `HUMAN_AGENT_TRANSFER_NUMBER`.
* Use PostgreSQL for production.
* Configure proper CORS and HTTPS.
* Monitor retrieval and resolution quality.
* Keep the Knowledge Base synchronized with Pinecone.
* Store ticket, retrieval, call, and resolution metadata for traceability.
* Do not rely blindly on LLM confidence; combine it with retrieval scores, validation, and business rules.

---

## Core Principle

```text
RAG        → Provides Knowledge
LLM        → Generates Responses
Agent      → Controls Workflow
Scheduler  → Controls Timing
Vonage     → Handles Communication
Database   → Preserves State
```

> **Retrieve first. Generate second. Verify resolution. Escalate when necessary.**
