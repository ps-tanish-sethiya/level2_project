# DevSentinel Architecture Specification

## System Overview

DevSentinel is an agentic AI assistant designed to automate software build failure diagnosis and PR risk evaluation. It decouples the core ReAct reasoning agent from tool execution via a Model Context Protocol (MCP) server running over stdio transport.

---

## 🏗️ End-to-End System Architecture

```
 ┌─────────────────────────────────────────────────────────────┐
 │                      DevSentinel CLI                        │
 │                  (cli/main.py Interactive)                  │
 └──────────────────────────────┬──────────────────────────────┘
                                │ Query & Trajectory Logs
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                     DevSentinel Agent                       │
 │                    (agent/agent.py ReAct)                   │
 └──────────────┬──────────────────────────────┬───────────────┘
                │ LLM Query / Response         │ Tool Invocation
                ▼                              ▼
 ┌─────────────────────────────┐  ┌────────────────────────────┐
 │      Dual LLM Provider      │  │     Custom MCP Server      │
 │    (agent/llm_provider.py)  │  │   (mcp_server/server.py)   │
 │                             │  │                            │
 │  Primary: Gemini 2.5 Flash  │  │  STDIO Transport (FastMCP) │
 │  Fallback: Groq Llama-3.3   │  └─────────────┬──────────────┘
 └─────────────────────────────┘                │ Dispatches
                                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                       9 MCP Tools                           │
 ├──────────────────────────────┬──────────────────────────────┤
 │  Live External APIs          │  Local Data Stores           │
 │  - get_build_status          │  - search_error_kb (Chroma)  │
 │  - get_build_logs            │  - get_past_incidents (SQLite│
 │  - check_dep_vulnerabilities │  - log_new_incident (SQLite) │
 │  - get_package_info          │                              │
 │  - get_recent_commits        │                              │
 │  - check_service_status      │                              │
 └──────────────────────────────┴──────────────────────────────┘
```

---

## 🧱 Component Breakdown

### 1. ReAct Agent Engine (`agent/agent.py`)
- **Reason → Act → Observe Loop**: Manages multi-turn reasoning context, capping trajectory at 8 iterations to prevent infinite loops.
- **Human-in-the-Loop Safeguard**: Intercepts `log_new_incident` calls, prompting operator for explicit `y/n` confirmation before modifying SQLite database.

### 2. Dual LLM Provider Layer (`agent/llm_provider.py`)
- **Primary**: Google Gemini 2.5 Flash (`google-generativeai` SDK).
- **Fallback**: Groq Llama-3.3-70b-versatile (`groq` SDK).
- **Failover Logic**: Explicitly catches HTTP 429 (rate limits), 15s timeouts, 5xx server errors, or connection exceptions on Gemini, seamlessly failing over to Groq.

### 3. MCP Server & Tool Registry (`mcp_server/`)
- **Stdio Transport**: Registered via official Python `mcp` SDK `FastMCP`.
- **Structured Schema Enforcement**: All 9 tools enforce strict input/output Pydantic schemas.
- **Resource Exposure**: `data/kb/*.md` files exposed as static read-only resources (`kb://{filename}`).

### 4. Local Vector KB & RAG Store (`data/chroma_store`)
- Embedded ChromaDB vector store powered by `sentence-transformers/all-MiniLM-L6-v2` running locally on CPU ($0 API cost).
- Vector similarity threshold of `0.35` filters out weak matches.

### 5. Historical Incident Database (`data/incidents.db`)
- Embedded SQLite database storing synthetic and newly confirmed incident records.
