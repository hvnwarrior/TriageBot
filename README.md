# TriageBot

A private, AI-powered IT assistant for small teams: employees get help in
the channel they already use, IT gets documented tickets and a full audit
trail, and nobody has to start from scratch.

Employees chat with the assistant naturally (Slack, Teams, or a simple web
demo) when they have an IT problem. The assistant asks clarifying
questions, searches the company's IT knowledge base, and attempts to
resolve the issue without a technician. Every conversation — resolved or
not — ends in a fully documented ticket. IT can watch live conversations,
join, or take over at any point.

## How it works

**Flow:** employee message -> triage -> knowledge-base retrieval -> LLM
response -> resolution or escalation -> ticket -> audit log.

- **Three-tier triage.** Security-looking messages (phishing, malware,
  lost devices) escalate to a critical ticket immediately, before any
  other processing. Known low-risk issues (password resets, VPN setup)
  get instant self-serve answers from the knowledge base. Everything else
  goes through assisted troubleshooting.
- **The assistant refuses to guess.** Missing required details are asked
  for, never fabricated. After a configurable number of clarifying
  exchanges without resolution, the assistant escalates with the complete
  troubleshooting history attached.
- **Every outcome is documented.** Self-serve resolutions and escalations
  both produce tickets containing the problem, the full conversation
  history, severity, and employee/device info. Technicians never ask an
  employee to repeat what the assistant already covered.
- **IT stays in control.** Any conversation can be watched live, joined
  by a technician, or taken over completely — after a takeover the
  assistant stays silent until IT hands it back. Interventions are
  recorded in the audit log.
- **Append-only audit log.** Every classification, reply, escalation,
  ticket, and human intervention is recorded with timestamps and actors
  in a JSONL log that survives database resets.

## Architecture

```
backend/app/
├── api/                  # FastAPI routers
│   ├── assistant.py      #   employee-facing: send message, history
│   ├── it_console.py     #   IT-facing: tickets, audit, watch/join/takeover
│   ├── documents.py      #   knowledge base upload/indexing
│   └── health.py
├── adapters/
│   └── slack_adapter.py  # Slack Socket Mode integration (optional)
├── services/
│   ├── support_assistant_service.py  # orchestration of the full flow
│   ├── triage_service.py             # three-tier classification
│   ├── ticket_service.py             # tickets for every outcome
│   ├── audit_service.py              # append-only JSONL audit log
│   ├── takeover_service.py           # live IT oversight state
│   ├── conversation_service.py       # conversation/message storage
│   ├── anthropic_service.py          # LLM calls
│   ├── search_service.py             # RAG search
│   ├── embedding_service.py          # local sentence-transformers
│   ├── vector_store.py               # ChromaDB
│   └── document_*                    # knowledge base ingestion
└── main.py
frontend/                   # chat demo wired to the assistant API
scripts/
└── demo_conversation.py    # scripted end-to-end demo (3 scenarios)
tests/
└── test_services.py        # smoke tests: triage, tickets, audit, takeover
```

**Storage:** SQLite for conversations and tickets, JSONL for the audit
log, ChromaDB for knowledge-base vectors. Everything runs locally or on
infrastructure you own — no third-party SaaS in the data path.

## Running it

With Docker (recommended):

```bash
cp .env.example .env          # set TRIAGEBOT_ANTHROPIC_API_KEY
docker compose up
# frontend on http://localhost:8080, API on http://localhost:8000/docs
```

Without Docker:

```bash
cp .env.example .env          # set TRIAGEBOT_ANTHROPIC_API_KEY
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Load the knowledge base (`docs/` is pre-organized into categories like
`microsoft/`, `jamf/`, `powershell/`) via the documents API.

**Scripted demo** (works without the server or UI):

```bash
cd backend
python -m scripts.demo_conversation
```

**Slack adapter** (optional):

```bash
pip install -r requirements-slack.txt
export SLACK_BOT_TOKEN=... SLACK_APP_TOKEN=...
python -m app.adapters.slack_adapter
```

**Tests:**

```bash
cd backend
pip install -r requirements-test.txt
pytest
```

## API highlights

| Endpoint | What it does |
| --- | --- |
| `POST /assistant/message` | Employee sends a message; full flow runs |
| `GET /it/conversations/active` | IT sees live conversations |
| `POST /it/conversations/{id}/takeover` | IT takes over; assistant silences |
| `GET /it/tickets` | Ticket queue with statuses |
| `GET /it/audit` | Audit trail, optionally per conversation |

## Design principles

1. **Security-first routing.** Possible incidents reach a human before
   anything else happens. IT is a sensor for security, not just a
   helpdesk.
2. **Refusal over fabrication.** An invented access scope or OS version
   isn't a typo; it's a wrong answer delivered confidently. The assistant
   asks instead of guessing.
3. **Every path is auditable.** If the automation did it, the log says
   so — timestamps and usernames on every action, including failures.
4. **Humans stay in the loop where it matters.** The assistant handles
   the repetitive parts; IT can watch and intervene at any moment.
