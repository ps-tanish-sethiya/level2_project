"""
Unit tests for each of the 9 DevSentinel MCP tools in isolation.
"""

import os
import pytest
import sqlite3
from unittest.mock import patch, MagicMock

from mcp_server.tools.live_build_tools import get_build_status, get_build_logs
from mcp_server.tools.live_security_tools import check_dependency_vulnerabilities, get_package_info
from mcp_server.tools.live_repo_tools import get_recent_commits, check_service_status
from mcp_server.tools.local_kb_tools import search_error_kb
from mcp_server.tools.local_incident_tools import get_past_incidents, log_new_incident


# 1. get_build_status
def test_get_build_status():
    result = get_build_status("ps-tanish-sethiya/demo-target-repo", "main")
    assert isinstance(result, dict)
    assert "status" in result
    assert "conclusion" in result
    assert "run_id" in result


# 2. get_build_logs
def test_get_build_logs():
    result = get_build_logs("ps-tanish-sethiya/demo-target-repo", "12345678")
    assert isinstance(result, dict)
    assert "extracted_error" in result
    assert "raw_log_excerpt" in result


# 3. check_dependency_vulnerabilities
def test_check_dependency_vulnerabilities():
    # Test with pyyaml 5.1 known CVE package
    result = check_dependency_vulnerabilities("pyyaml", "5.1", "PyPI")
    assert isinstance(result, dict)
    assert "vulnerable" in result
    assert "cve_ids" in result
    assert "severity" in result
    assert "summary" in result


# 4. get_package_info
def test_get_package_info():
    result = get_package_info("requests", "pypi")
    assert isinstance(result, dict)
    assert "latest_version" in result
    assert result["latest_version"] != "unknown"
    assert "current_release_date" in result


# 5. get_recent_commits
def test_get_recent_commits():
    result = get_recent_commits("ps-tanish-sethiya/demo-target-repo", limit=3)
    assert isinstance(result, dict)
    assert "commits" in result
    assert isinstance(result["commits"], list)


# 6. check_service_status
def test_check_service_status():
    result = check_service_status("github")
    assert isinstance(result, dict)
    assert "service" in result
    assert result["service"] == "GitHub"
    assert "status" in result


# 7. search_error_kb
def test_search_error_kb():
    result = search_error_kb("AssertionError: Expected 200 OK", top_k=2)
    assert isinstance(result, dict)
    assert "matches" in result
    assert isinstance(result["matches"], list)


# 8 & 9. get_past_incidents and log_new_incident
def test_local_incident_tools(tmp_path):
    db_file = tmp_path / "test_incidents.db"
    
    # Pre-create schema
    init_conn = sqlite3.connect(db_file)
    init_conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT NOT NULL,
            summary TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            resolution TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    init_conn.close()

    def get_test_conn():
        c = sqlite3.connect(db_file)
        c.row_factory = sqlite3.Row
        return c
    
    with patch("mcp_server.tools.local_incident_tools._get_db_connection", side_effect=get_test_conn):
        
        # Test log_new_incident
        log_res = log_new_incident(
            component="auth-service",
            summary="JWT token expiration failure",
            root_cause="Clock drift across server nodes",
            resolution="Configured NTP service daemon"
        )
        assert log_res["success"] is True
        assert log_res["incident_id"] is not None
        
        # Test get_past_incidents
        fetch_res = get_past_incidents(component="auth-service")
        assert isinstance(fetch_res, dict)
        assert len(fetch_res["incidents"]) == 1
        assert fetch_res["incidents"][0]["component"] == "auth-service"
        assert fetch_res["incidents"][0]["root_cause"] == "Clock drift across server nodes"
