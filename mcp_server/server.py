"""
MCP (Model Context Protocol) Server for DevSentinel.
Uses official `mcp` SDK (stdio transport) to register diagnostic tools and KB markdown resources.
"""

import os
import sys
import glob
import logging
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP

# Ensure project root is in sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import all tool handlers
from mcp_server.tools.live_build_tools import get_build_status, get_build_logs
from mcp_server.tools.live_security_tools import check_dependency_vulnerabilities, get_package_info
from mcp_server.tools.live_repo_tools import get_recent_commits, check_service_status
from mcp_server.tools.local_kb_tools import search_error_kb
from mcp_server.tools.local_incident_tools import get_past_incidents, log_new_incident

# Initialize FastMCP Server
mcp = FastMCP("DevSentinel MCP Server")

# ---------------------------------------------------------------------------
# Tool Registrations
# ---------------------------------------------------------------------------

@mcp.tool(
    name="get_build_status",
    description="Get the latest build run status (status, conclusion, run_id, commit_sha) from GitHub Actions for a repository."
)
def tool_get_build_status(repo: str, branch: str = "main") -> Dict[str, Any]:
    return get_build_status(repo=repo, branch=branch)


@mcp.tool(
    name="get_build_logs",
    description="Fetch and parse GitHub Actions workflow failure log lines and excerpt for a specific run ID."
)
def tool_get_build_logs(repo: str, run_id: str) -> Dict[str, Any]:
    return get_build_logs(repo=repo, run_id=run_id)


@mcp.tool(
    name="check_dependency_vulnerabilities",
    description="Query OSV.dev database for known CVE vulnerabilities given a package, version, and ecosystem."
)
def tool_check_dependency_vulnerabilities(package: str, version: str, ecosystem: str = "PyPI") -> Dict[str, Any]:
    return check_dependency_vulnerabilities(package=package, version=version, ecosystem=ecosystem)


@mcp.tool(
    name="get_package_info",
    description="Fetch registry release date, latest version, and deprecation status for PyPI or npm package."
)
def tool_get_package_info(package: str, ecosystem: str = "pypi") -> Dict[str, Any]:
    return get_package_info(package=package, ecosystem=ecosystem)


@mcp.tool(
    name="get_recent_commits",
    description="Fetch recent commit messages, authors, and SHAs for a given GitHub repository."
)
def tool_get_recent_commits(repo: str, limit: int = 5) -> Dict[str, Any]:
    return get_recent_commits(repo=repo, limit=limit)


@mcp.tool(
    name="check_service_status",
    description="Check operational status of external infrastructure services (e.g. GitHub Status API)."
)
def tool_check_service_status(service: str = "github") -> Dict[str, Any]:
    return check_service_status(service=service)


@mcp.tool(
    name="search_error_kb",
    description="Search local vector knowledge base (ChromaDB) for matching error symptoms and recommended fixes."
)
def tool_search_error_kb(error_text: str, top_k: int = 3) -> Dict[str, Any]:
    return search_error_kb(error_text=error_text, top_k=top_k)


@mcp.tool(
    name="get_past_incidents",
    description="Retrieve past incident records from SQLite database matching component or recent timeline."
)
def tool_get_past_incidents(component: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    return get_past_incidents(component=component, limit=limit)


@mcp.tool(
    name="log_new_incident",
    description="Log a newly diagnosed incident into SQLite database. REQUIRES prior user confirmation."
)
def tool_log_new_incident(component: str, summary: str, root_cause: str, resolution: str) -> Dict[str, Any]:
    return log_new_incident(component=component, summary=summary, root_cause=root_cause, resolution=resolution)


# ---------------------------------------------------------------------------
# MCP Resources Registration (Demonstrating Tools vs. Resources distinction)
# Exposes raw markdown KB articles as static read-only resources
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KB_DIR = os.path.join(PROJECT_ROOT, "data", "kb")

@mcp.resource("kb://{filename}")
def get_kb_article_resource(filename: str) -> str:
    """
    Expose data/kb/*.md files as MCP resources.
    """
    safe_filename = os.path.basename(filename)
    if not safe_filename.endswith(".md"):
        safe_filename += ".md"
        
    file_path = os.path.join(KB_DIR, safe_filename)
    if not os.path.exists(file_path):
        return f"# Error\nKnowledge base article '{filename}' not found."
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"# Error reading resource '{filename}': {str(e)}"


if __name__ == "__main__":
    # Run stdio transport server
    mcp.run()
