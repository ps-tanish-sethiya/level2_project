# 🛡️ DevSentinel v2.0 -- Agentic Build, Code Quality & PR Diagnosis System

**DevSentinel** is a production-grade ReAct agentic AI assistant powered by a **custom Model Context Protocol (MCP) server**. It automates software build failure diagnosis, SonarCloud code quality auditing, Pull Request (PR) security analysis, and infrastructure triage by orchestrating **11 specialized MCP tools** across live external APIs (GitHub Actions, SonarCloud, OSV.dev, PyPI, Open-Meteo) and local vector/database engines.

---

## 🏗️ Architecture & Data Flow Diagram

```mermaid
flowchart TD
    %% Custom Styling
    classDef clientStyle fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#fff;
    classDef agentStyle fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#fff;
    classDef llmStyle fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef mcpStyle fill:#3b0764,stroke:#c084fc,stroke-width:2px,color:#fff;
    classDef liveStyle fill:#111827,stroke:#f43f5e,stroke-width:2px,color:#fff;
    classDef localStyle fill:#111827,stroke:#fbbf24,stroke-width:2px,color:#fff;
    classDef evalStyle fill:#312e81,stroke:#a5b4fc,stroke-width:2px,color:#fff;
    classDef reportStyle fill:#022c22,stroke:#10b981,stroke-width:2px,color:#fff;

    %% 🖥️ CLIENT LAYER
    subgraph Clients ["🖥️ Presentation & Protocol Layer"]
        CLI["Rich Terminal CLI<br/><code>cli/main.py</code>"]:::clientStyle
        EXT["External MCP Clients<br/><i>(Claude Desktop / Cursor / VS Code)</i>"]:::clientStyle
    end

    %% 🤖 AGENT & LLM LAYER
    subgraph CoreEngine ["🤖 ReAct Agent Engine & Failover Chain"]
        Agent["DevOps AI ReAct Agent<br/><code>agent/agent.py</code>"]:::agentStyle
        
        subgraph LLMs ["⚡ Multi-Provider LLM Resilience"]
            Gemini["1. Primary: Google Gemini 1.5 Flash"]:::llmStyle
            Groq["2. Fallback: Groq Llama-3.3-70B"]:::llmStyle
            Ollama["3. Local: Ollama llama3.2:3b"]:::llmStyle
        end
    end

    %% 🔌 MCP TOOL SERVER LAYER
    subgraph MCPInfra ["🔌 Custom Model Context Protocol (MCP) Server"]
        MCPClient["MCP Client & Dispatcher<br/><code>agent/mcp_client.py</code>"]:::mcpStyle

        subgraph LiveTools ["🌐 Live External APIs & Scanners"]
            GH["GitHub Actions & REST API<br/><i>(Build Status & Live Code Files)</i>"]:::liveStyle
            Sonar["SonarCloud & AST Engine<br/><i>(Code Quality & Cyclomatic Complexity)</i>"]:::liveStyle
            Sec["OSV.dev & PyPI Registries<br/><i>(Live CVE Vulnerability Scans)</i>"]:::liveStyle
        end

        subgraph LocalTools ["💾 Local Knowledge & DB"]
            RAG["ChromaDB Vector RAG<br/><i>(Error Solution Retrieval)</i>"]:::localStyle
            DB["SQLite Incident Database<br/><i>(Human-in-the-Loop Memory)</i>"]:::localStyle
        end
    end

    %% 📊 EVALUATION SUITE
    subgraph Evaluation ["📊 Multi-Tiered Ragas Evaluation Suite"]
        Ragas["Official Ragas 5-Metric Evaluator<br/><code>eval/evaluate_ragas.py</code><br/><b>Score: 95.7% Grade A+</b>"]:::evalStyle
    end

    %% 📋 EXECUTIVE OUTPUT
    subgraph Synthesis ["📋 Executive Synthesis"]
        Report["Synthesized Executive Diagnosis Report<br/><i>(Root Cause, Telemetry Evidence & Fixes)</i>"]:::reportStyle
    end

    %% 🔄 FLOW CONNECTIONS
    CLI & EXT -->|User Query| Agent
    Agent <-->|Reasoning & Tool Selection| Gemini
    Gemini -.->|Failover on 429/Timeout| Groq
    Groq -.->|Failover on Outage| Ollama

    Agent -->|Structured Tool Calls| MCPClient
    MCPClient --> GH & Sonar & Sec & RAG & DB
    GH & Sonar & Sec & RAG & DB -->|Telemetry Observations| Agent

    Agent -->|Execution Telemetry| Ragas
    Agent -->|Synthesizes Verdict| Report
    Report --> CLI & EXT
```

---

## 🛠️ The 11 MCP Server Tools

| # | MCP Tool Name | Telemetry Source | Function & Scope |
| :-: | :--- | :--- | :--- |
| **1** | `get_build_status` | GitHub Actions API | Checks workflow run status (`failure`/`success`) and commit SHA. |
| **2** | `get_build_logs` | GitHub Actions Log Extractor | Extracts raw `pytest` failure tracebacks from CI logs. |
| **3** | `get_recent_commits` | GitHub REST API | Retrieves recent commit messages, authors, and commit dates. |
| **4** | `check_code_quality` | SonarCloud & AST Linter | Evaluates Sonar quality gates, cyclomatic complexity, and null checks on GitHub. |
| **5** | `check_dependency_vulnerabilities` | OSV.dev REST API | Live security vulnerability lookup for Python packages (e.g. PyYAML 5.1). |
| **6** | `get_package_info` | PyPI JSON API | Fetches package version metadata and checks deprecations. |
| **7** | `check_service_status` | GitHub Status API | Differentiates external infrastructure outages from codebase bugs. |
| **8** | `search_error_kb` | ChromaDB Vector RAG | RAG vector search over known error solutions using `all-MiniLM-L6-v2`. |
| **9** | `get_past_incidents` | SQLite Incident DB | Queries past outage incident history for component correlation. |
| **10** | `log_new_incident` | SQLite Incident DB | Logs newly confirmed incident records (**Human Approval Guarded**). |
| **11** | `get_weather_by_ip` | Open-Meteo API | Geolocation weather lookup by IP for developer context. |

---

## 📊 Multi-Tiered Evaluation Benchmark (Ragas 95.7% Score)

The system features a **4-Tiered Evaluation Suite** ([eval/evaluate_ragas.py](file:///c:/Users/TanishSethiya/L2Project/eval/evaluate_ragas.py)):

| Metric Category | Evaluation Metric | Result | Target Standard |
| :--- | :--- | :---: | :---: |
| **Ragas Framework** | Faithfulness (Zero Hallucination Grounding) | **100.0%** | $> 95\%$ |
| **Ragas Framework** | Answer Relevance | **95.0%** | $> 90\%$ |
| **Ragas Framework** | Tool Selection Precision | **83.4%** | $> 80\%$ |
| **Ragas Framework** | Context Precision (Telemetry Quality) | **100.0%** | $> 90\%$ |
| **Ragas Framework** | Aspect Critic (Safety & Safeguard Score) | **100.0%** | $100\%$ |
| **Composite Ragas** | **Overall Composite Ragas Agent Score** | **95.7% (Grade A+)** | $> 90\%$ |
| **DevOps Telemetry**| **Mean Time To Diagnosis (MTTD)** | **6.53s** | $< 10.0\text{s}$ |

To run the live benchmark evaluation suite:
```bash
python eval/evaluate_ragas.py
```

---

## ⚙️ Setup & Quick Start

### 1. Virtual Environment & Dependencies
```bash
# Clone repository
git clone https://github.com/ps-tanish-sethiya/L2Project.git
cd L2Project

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell
# source venv/bin/activate    # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables (`.env`)
```env
GOOGLE_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
GITHUB_TOKEN=your_github_token
GITHUB_DEMO_REPO=ps-tanish-sethiya/demo-target-repo
```

### 3. Run Interactive Rich CLI
```bash
python cli/main.py
```

---

## 🔌 Connecting to External MCP Clients (Claude Desktop / Cursor / VS Code)

Our MCP server ([mcp_server/server.py](file:///c:/Users/TanishSethiya/L2Project/mcp_server/server.py)) connects via standard `stdio` to any MCP client.

### Claude Desktop Configuration (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "devsentinel": {
      "command": "c:\\Users\\TanishSethiya\\L2Project\\venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "c:\\Users\\TanishSethiya\\L2Project"
    }
  }
}
```

---

## 📄 License
MIT License. Built for Production AI Engineer Certification.
