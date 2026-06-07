# soill

Shared library for the SOILL Public RAG Chatbot (Postgres/pgvector, Mistral, chunking, RAG).

Key modules:

| Module | Purpose |
|--------|---------|
| `services/chat_service.py` | `ChatService` — orchestration for Chainlit and FastAPI |
| `rag.py` | Retrieval and Mistral chat completion |
| `store_pg.py` | Postgres/pgvector storage |
| `citations.py` | Parse citation markers from answers |
| `conversation_log.py` | Persist Q&A to `soill_conversations` |

*Author:* Professor Stephen Hallett, 5 June, 2026
