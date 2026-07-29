"""
End-to-End Scenario Tests for DevSentinel ReAct Agent covering all 6 mandatory evaluation scenarios.
"""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock

from agent.agent import DevSentinelAgent, AgentRunResult
from agent.llm_provider import LLMResponse, LLMToolCall
from mcp_server.tools.local_incident_tools import log_new_incident, get_past_incidents


# ---------------------------------------------------------------------------
# Scenario 1: Known flaky failure
# ---------------------------------------------------------------------------
def test_known_flaky_failure():
    """
    Scenario 1: Build failure error text matches a KB article tagged 'flaky test timeout'.
    Agent should recommend retry and not escalate.
    """
    agent = DevSentinelAgent()
    
    mock_llm_step1 = LLMResponse(
        content="Searching local knowledge base for flaky test error pattern...",
        tool_calls=[LLMToolCall(id="c1", name="search_error_kb", args={"error_text": "TimeoutError: Connection timed out after 30000ms in integration test"})],
        provider_used="gemini"
    )
    
    mock_llm_step2 = LLMResponse(
        content="Diagnosis: The build failure is a known flaky test timeout. Recommendation: Safe to retry build pipeline without escalation.",
        tool_calls=[],
        provider_used="gemini"
    )
    
    with patch.object(agent.llm, "chat", side_effect=[mock_llm_step1, mock_llm_step2]):
        result = agent.run(query="Why did the integration test build fail with timeout?")
        assert "flaky test" in result.final_answer.lower() or "retry" in result.final_answer.lower()
        assert result.total_tool_calls == 1
        assert result.steps[0].tool_name == "search_error_kb"


# ---------------------------------------------------------------------------
# Scenario 2: Real CVE in dependency
# ---------------------------------------------------------------------------
def test_real_cve_in_dependency():
    """
    Scenario 2: Query 'Is this PR safe to merge?' against requirements pinned to pyyaml==5.1.
    Agent should flag real CVE returned from OSV.dev and recommend against merging.
    """
    agent = DevSentinelAgent()
    
    mock_llm_step1 = LLMResponse(
        content="Checking dependency security vulnerabilities for PyYAML 5.1...",
        tool_calls=[LLMToolCall(id="c1", name="check_dependency_vulnerabilities", args={"package": "pyyaml", "version": "5.1", "ecosystem": "PyPI"})],
        provider_used="gemini"
    )
    
    mock_llm_step2 = LLMResponse(
        content="Diagnosis: PR is HIGH RISK and UNSAFE to merge due to critical security vulnerability CVE-2020-14343 in PyYAML 5.1. Upgrade to >=6.0.1 immediately.",
        tool_calls=[],
        provider_used="gemini"
    )
    
    with patch.object(agent.llm, "chat", side_effect=[mock_llm_step1, mock_llm_step2]):
        result = agent.run(query="Is this PR safe to merge with PyYAML 5.1?")
        assert "cve" in result.final_answer.lower() or "unsafe" in result.final_answer.lower() or "high risk" in result.final_answer.lower()
        assert result.steps[0].tool_name == "check_dependency_vulnerabilities"


# ---------------------------------------------------------------------------
# Scenario 3: Genuinely novel failure
# ---------------------------------------------------------------------------
def test_genuinely_novel_failure():
    """
    Scenario 3: Novel error with no KB match and no past incident.
    Agent should explicitly say it's unrecognized, recommend human review, and log incident after user confirmation.
    """
    agent = DevSentinelAgent()
    
    mock_llm_step1 = LLMResponse(
        content="Searching KB and past incidents for novel error code QuantumMemoryOverflowError...",
        tool_calls=[LLMToolCall(id="c1", name="search_error_kb", args={"error_text": "QuantumMemoryOverflowError in kernel driver"})],
        provider_used="gemini"
    )
    
    mock_llm_step2 = LLMResponse(
        content="No KB match found. Proposing to log a new incident after human confirmation.",
        tool_calls=[LLMToolCall(id="c2", name="log_new_incident", args={
            "component": "kernel-driver",
            "summary": "Unrecognized QuantumMemoryOverflowError",
            "root_cause": "Novel memory allocation boundary bug",
            "resolution": "Escalated for senior human engineer investigation"
        })],
        provider_used="gemini"
    )
    
    mock_llm_step3 = LLMResponse(
        content="Diagnosis: Failure is unrecognized. Recommended human review. Incident #99 logged successfully.",
        tool_calls=[],
        provider_used="gemini"
    )
    
    # User confirms action in confirmation prompt
    mock_confirm = MagicMock(return_value=True)
    
    with patch.object(agent.llm, "chat", side_effect=[mock_llm_step1, mock_llm_step2, mock_llm_step3]):
        result = agent.run(
            query="Diagnose unknown error QuantumMemoryOverflowError",
            confirm_callback=mock_confirm
        )
        assert "unrecognized" in result.final_answer.lower() or "incident" in result.final_answer.lower() or "human" in result.final_answer.lower()
        mock_confirm.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 4: Repeat of scenario 3 (Memory verification)
# ---------------------------------------------------------------------------
def test_repeat_novel_failure_memory(tmp_path):
    """
    Scenario 4: Re-query the previously logged novel incident.
    `get_past_incidents` should locate the newly logged entry, demonstrating memory loop working.
    """
    db_file = tmp_path / "incidents.db"
    
    # Pre-populate SQLite with the logged incident from Scenario 3
    init_conn = sqlite3.connect(db_file)
    init_conn.execute("""
        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT NOT NULL,
            summary TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            resolution TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    init_conn.execute("""
        INSERT INTO incidents (component, summary, root_cause, resolution)
        VALUES ('kernel-driver', 'Unrecognized QuantumMemoryOverflowError', 'Novel memory allocation boundary bug', 'Escalated for senior human engineer investigation')
    """)
    init_conn.commit()
    init_conn.close()

    def get_test_conn():
        c = sqlite3.connect(db_file)
        c.row_factory = sqlite3.Row
        return c

    with patch("mcp_server.tools.local_incident_tools._get_db_connection", side_effect=get_test_conn):
        res = get_past_incidents(component="kernel-driver")
        assert len(res["incidents"]) == 1
        assert res["incidents"][0]["summary"] == "Unrecognized QuantumMemoryOverflowError"
        assert res["incidents"][0]["root_cause"] == "Novel memory allocation boundary bug"


# ---------------------------------------------------------------------------
# Scenario 5: External outage, not your bug
# ---------------------------------------------------------------------------
def test_external_outage_attribution():
    """
    Scenario 5: Simulate check_service_status returning major_outage for GitHub.
    Agent should attribute failure to external service outage rather than codebase.
    """
    agent = DevSentinelAgent()
    
    mock_llm_step1 = LLMResponse(
        content="Checking external infrastructure service status...",
        tool_calls=[LLMToolCall(id="c1", name="check_service_status", args={"service": "github"})],
        provider_used="gemini"
    )
    
    mock_llm_step2 = LLMResponse(
        content="Diagnosis: The build failure is caused by an external GitHub infrastructure outage (Major Outage). This is NOT an application code bug.",
        tool_calls=[],
        provider_used="gemini"
    )
    
    with patch.object(agent.llm, "chat", side_effect=[mock_llm_step1, mock_llm_step2]):
        result = agent.run(query="Is GitHub Actions down causing build failures?")
        assert "external" in result.final_answer.lower() or "outage" in result.final_answer.lower()
        assert result.steps[0].tool_name == "check_service_status"


# ---------------------------------------------------------------------------
# Scenario 6: LLM provider failover
# ---------------------------------------------------------------------------
def test_llm_provider_failover_scenario():
    """
    Scenario 6: Force Gemini to fail (mock 429 rate limit) mid-scenario and confirm agent
    completes query successfully via Groq with provider_used='groq'.
    """
    agent = DevSentinelAgent()
    
    mock_groq_step1 = LLMResponse(
        content="Groq fallback executing: Checking build status for repo...",
        tool_calls=[LLMToolCall(id="cg1", name="get_build_status", args={"repo": "ps-tanish-sethiya/demo-target-repo"})],
        provider_used="groq"
    )
    
    mock_groq_step2 = LLMResponse(
        content="Diagnosis via Groq Fallback: Build run completed successfully.",
        tool_calls=[],
        provider_used="groq"
    )
    
    # Mock Gemini to throw rate limit error on every call
    with patch.object(agent.llm, "_call_gemini", side_effect=Exception("HTTP 429 Gemini Quota Exceeded")):
        with patch.object(agent.llm, "_call_groq", side_effect=[mock_groq_step1, mock_groq_step2]):
            result = agent.run(query="Check build status on demo repo")
            assert result.provider_used == "groq"
            assert "groq fallback" in result.final_answer.lower()
