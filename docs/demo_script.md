# DevSentinel Live Demo Script

Use this step-by-step walkthrough to demonstrate DevSentinel to a reviewer.

---

## 🚀 Pre-Demo Checklist

1. Ensure virtual environment is activated:
   - **Windows**: `.\venv\Scripts\Activate.ps1`
   - **macOS/Linux**: `source venv/bin/activate`
2. Confirm `.env` has valid `GOOGLE_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`, and `GITHUB_DEMO_REPO`.
3. Verify local data is seeded:
   ```bash
   python data/seed_data.py
   ```

---

## 🎬 Live Demo Scenarios

### Scenario 1: Known Flaky Test Failure
- **Command**: `python cli/main.py "Why did the integration test build fail with a timeout?"`
- **Expected Demo Behavior**:
  - Agent calls `search_error_kb`.
  - Matches article `Flaky Test Timeout in CI Pipeline` (similarity > 0.35).
  - Recommends increasing wait timeout or marking `@pytest.mark.flaky(reruns=2)`. State: "Safe to retry, no escalation needed."

---

### Scenario 2: Real CVE in Dependency
- **Command**: `python cli/main.py "Is this PR safe to merge with PyYAML 5.1 dependency?"`
- **Expected Demo Behavior**:
  - Agent calls `check_dependency_vulnerabilities(package='pyyaml', version='5.1')`.
  - OSV.dev returns live vulnerability `CVE-2020-14343` (High/Critical).
  - Utility risk score outputs **HIGH RISK** (score >= 50). Recommendation: "DO NOT MERGE. Block PR until upgraded."

---

### Scenario 3: Genuinely Novel Failure & Human Approval
- **Command**: `python cli/main.py "Diagnose unknown kernel driver QuantumMemoryOverflowError"`
- **Expected Demo Behavior**:
  - Agent searches KB (`search_error_kb`) and past incidents (`get_past_incidents`). No matches found.
  - Agent honestly states: "Failure is unrecognized. Recommending human engineer review."
  - Agent proposes calling `log_new_incident`.
  - **Human-in-the-Loop Prompt**: CLI displays proposed incident summary and waits for `[y/N]`. Type `y` to confirm.

---

### Scenario 4: Repeat of Novel Failure (Memory Verification)
- **Command**: `python cli/main.py "Check past incidents for QuantumMemoryOverflowError"`
- **Expected Demo Behavior**:
  - Agent calls `get_past_incidents(component='kernel-driver')`.
  - Immediately finds newly logged incident from Scenario 3. Demonstrates memory loop working.

---

### Scenario 5: External Outage Attribution
- **Command**: `python cli/main.py "Is GitHub Actions down causing build failures?"`
- **Expected Demo Behavior**:
  - Agent calls `check_service_status(service='github')`.
  - Attributes failure to external infrastructure outage rather than application code.

---

### Scenario 6: Gemini → Groq LLM Failover
- **Command**: `pytest -v tests/test_llm_provider.py`
- **Expected Demo Behavior**:
  - Demonstrates `test_gemini_rate_limit_failover_to_groq` transparently falling back to Groq Llama-3.3 when Gemini API encounters a simulated 429 rate limit error.
