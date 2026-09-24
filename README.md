# RAG Call Center Agent (Arabic)

An AI-powered Arabic customer support agent that combines **RAG, LLMs, automated follow-up calls, and human escalation** to resolve customer issues.

## 🚀 How It Works

```text
Customer Message
      ↓
   RAG Agent
      ↓
Knowledge Base Answer
      ↓
Schedule Follow-up Call (3 min)
      ↓
Customer Verification
      ↓
┌─────────────────────────────┐
│ Resolved? → Close Ticket    │
│ Not Resolved → Retry        │
└─────────────────────────────┘
      ↓
Attempt 2 → Broader RAG Search
      ↓
Attempt 3 → Tavily Web Search
      ↓
Still unresolved → Human Agent
```

## 🧠 Resolution Strategy

| Attempt | Strategy              |
| ------- | --------------------- |
| 1       | Narrow RAG retrieval  |
| 2       | Broader RAG retrieval |
| 3       | Web search + LLM      |
| Final   | Human escalation      |

* Follow-up delay: **180 seconds**
* Maximum resolution attempts: **3**
* Call retries are configurable.

## 🏗️ Project Structure

```text
rag-call-center-agent/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── db.py
│   ├── services/
│   │   ├── auth.py
│   │   ├── rag/
│   │   │   ├── embeddings.py
│   │   │   ├── vectorstore.py
│   │   │   ├── llm.py
│   │   │   └── web_search.py
│   │   └── agent/
│   │       ├── resolution_agent.py
│   │       ├── telephony.py
│   │       ├── verify.py
│   │       └── scheduler.py
│   └── routers/
│       ├── chat.py
│       ├── webhooks.py
│       ├── auth.py
│       ├── staff.py
│       ├── customer_auth.py
│       └── admin.py
├── static/
│   ├── index.html
│   └── admin.html
├── docs/
│   └── evaluation_and_metrics.md
├── seed_kb.py
├── kb_articles_sample.json
├── schema.sql
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 Tech Stack

* **FastAPI** — API & webhooks
* **Voyage AI** — embeddings
* **Pinecone** — vector database
* **OpenRouter** — LLM generation
* **Tavily** — web search
* **Vonage Voice** — outbound calls
* **Vonage Verify** — OTP authentication
* **SQLite / PostgreSQL** — persistence
* **ngrok** — local HTTPS webhooks

## 🔄 RAG Pipeline

```text
Knowledge Base
      ↓
Chunking
      ↓
Voyage Embeddings
      ↓
Pinecone
      ↓
User Query
      ↓
Vector Search
      ↓
Context
      ↓
LLM
      ↓
Answer
```

## 🔐 Authentication

### Staff

* JWT authentication
* `agent`
* `admin`
* `superadmin`

### Customer

* Phone + OTP
* JWT scoped to the customer's own data

## 📊 Evaluation

### RAG

* Recall@K
* Precision@K
* MRR
* Context Relevance
* Faithfulness
* Answer Relevance

### Agent

* Resolution Rate
* First-Attempt Resolution Rate
* Escalation Rate
* Call Success Rate
* Retry Rate
* Average Resolution Time

## ⚙️ Setup

```bash
git clone <YOUR_REPOSITORY_URL>
cd rag-call-center-agent

python -m venv .venv
```

Activate the environment:

```bash
# Windows
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env` from `.env.example`, configure the required API keys, then seed the knowledge base:

```bash
python seed_kb.py
```

Run the application:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

For Vonage webhooks:

```bash
ngrok http 8000
```

Set the generated HTTPS URL as `PUBLIC_BASE_URL`.

## 🔒 Production Notes

* Never commit `.env`.
* Change default admin credentials and JWT secret.
* Use PostgreSQL for production.
* Keep the vector database synchronized with the source knowledge base.
* Configure a real human-agent transfer number.
* Monitor retrieval, calls, and resolution metrics.

## 🎯 Core Principle

> **Retrieve first. Generate second. Verify resolution. Escalate when necessary.**
