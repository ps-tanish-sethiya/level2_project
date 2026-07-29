# DevSentinel

**DevSentinel** is a production-quality, ReAct-style agentic AI assistant backed by a custom Model Context Protocol (MCP) server. It diagnoses software build and Pull Request (PR) failures by combining live external API signals with local knowledge sources (SQLite incident database and ChromaDB RAG vector store).

---

## 🏗️ Architecture Overview

For full architectural details, see [`docs/architecture.md`](docs/architecture.md).

```
 ┌─────────────────────────────────────────────────────────────┐
 │                      DevSentinel CLI                        │
 └──────────────────────────────┬──────────────────────────────┘
                                │ Query & Interaction
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                       ReAct Agent Loop                      │
 └──────────────┬──────────────────────────────┬───────────────┘
                │ Dual LLM Provider            │ MCP Client
                ▼                              ▼
 ┌─────────────────────────────┐  ┌────────────────────────────┐
 │  LLM Provider Layer         │  │     Custom MCP Server      │
 │  (Gemini 2.5 Flash Primary  │  │   (stdio transport, std)   │
 │   + Groq Llama-3.3 Fallback)│  └─────────────┬──────────────┘
 └─────────────────────────────┘                │ Calls
                                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                          9 Tools                            │
 ├──────────────────────────────┬──────────────────────────────┤
 │ Live External APIs           │ Local Data Sources           │
 │  - get_build_status          │  - search_error_kb (Chroma)  │
 │  - get_build_logs            │  - get_past_incidents (SQLite│
 │  - check_dep_vulnerabilities │  - log_new_incident (SQLite) │
 │  - get_package_info          │                              │
 │  - get_recent_commits        │                              │
 │  - check_service_status      │                              │
 └──────────────────────────────┴──────────────────────────────┘
```

---

## ⚙️ Environment Setup & Installation

### Prerequisites
- Python 3.11+
- Git

### 1. Clone & Set Up Virtual Environment

#### Windows (PowerShell)
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### macOS / Linux (Bash)
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```powershell
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Edit `.env` and set your API keys:
- `GOOGLE_API_KEY`: Free key from [Google AI Studio](https://aistudio.google.com/)
- `GROQ_API_KEY`: Free key from [Groq Console](https://console.groq.com/)
- `GITHUB_TOKEN`: Fine-grained personal access token (read-only access to repository & actions)
- `GITHUB_DEMO_REPO`: `owner/repo` format for target repository

---

## 🚀 Running DevSentinel

### Step 1: Seed Local Data (SQLite + RAG Embeddings)
```bash
python data/seed_data.py
```

### Step 2: Run Interactive CLI
```bash
python cli/main.py
```

### Step 3: Run Unit & Scenario Tests
```bash
pytest -v tests/
```

---

## 🧪 Test Scenarios Supported
1. **Known Flaky Failure**: Identifies transient test timeouts and suggests safe retries.
2. **Real CVE in Dependency**: Detects vulnerable packages via live OSV.dev checks and blocks merge.
3. **Genuinely Novel Failure**: Recognizes unclassified issues, escalates to human review, and logs confirmed incidents.
4. **Memory Verification**: Re-tests novel failure to verify RAG/incident memory retrieval.
5. **External Service Outage**: Identifies external downtime (e.g., GitHub Status) vs application bugs.
6. **LLM Provider Failover**: Verifies Gemini -> Groq fallback on API rate limit or error.

---

## 📄 License
MIT License. Created for Internship Certification.
