"""
MCP Client Wrapper for DevSentinel Agent.
Fetches dynamic tool definitions and executes tool calls against mcp_server.
"""

import logging
from typing import List, Dict, Any

from mcp_server.tools.live_build_tools import get_build_status, get_build_logs
from mcp_server.tools.live_security_tools import check_dependency_vulnerabilities, get_package_info
from mcp_server.tools.live_repo_tools import get_recent_commits, check_service_status
from mcp_server.tools.local_kb_tools import search_error_kb
from mcp_server.tools.local_incident_tools import get_past_incidents, log_new_incident

logger = logging.getLogger("devsentinel.agent.mcp_client")


class MCPClientWrapper:
    """
    Client connecting agent loop dynamically to registered MCP server tools.
    """
    def __init__(self):
        self._tool_registry = {
            "get_build_status": {
                "func": get_build_status,
                "schema": {
                    "name": "get_build_status",
                    "description": "Get latest build run status (status, conclusion, run_id, commit_sha) from GitHub Actions for a repo.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "Repository name in 'owner/repo' format"},
                            "branch": {"type": "string", "description": "Branch name (default 'main')"}
                        },
                        "required": ["repo"]
                    }
                }
            },
            "get_build_logs": {
                "func": get_build_logs,
                "schema": {
                    "name": "get_build_logs",
                    "description": "Fetch and parse GitHub Actions workflow failure log lines and excerpt for a specific run ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "Repository name in 'owner/repo' format"},
                            "run_id": {"type": "string", "description": "Workflow run ID"}
                        },
                        "required": ["repo", "run_id"]
                    }
                }
            },
            "check_dependency_vulnerabilities": {
                "func": check_dependency_vulnerabilities,
                "schema": {
                    "name": "check_dependency_vulnerabilities",
                    "description": "Query OSV.dev database for known CVE vulnerabilities given a package, version, and ecosystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "package": {"type": "string", "description": "Package name e.g. pyyaml"},
                            "version": {"type": "string", "description": "Version string e.g. 5.1"},
                            "ecosystem": {"type": "string", "description": "Package ecosystem e.g. PyPI, npm"}
                        },
                        "required": ["package", "version"]
                    }
                }
            },
            "get_package_info": {
                "func": get_package_info,
                "schema": {
                    "name": "get_package_info",
                    "description": "Fetch registry release date, latest version, and deprecation status for PyPI or npm package.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "package": {"type": "string", "description": "Package name e.g. requests"},
                            "ecosystem": {"type": "string", "description": "Ecosystem 'pypi' or 'npm'"}
                        },
                        "required": ["package"]
                    }
                }
            },
            "get_recent_commits": {
                "func": get_recent_commits,
                "schema": {
                    "name": "get_recent_commits",
                    "description": "Fetch recent commit messages, authors, and SHAs for a given GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "Repository name in 'owner/repo' format"},
                            "limit": {"type": "integer", "description": "Max commits to return"}
                        },
                        "required": ["repo"]
                    }
                }
            },
            "check_service_status": {
                "func": check_service_status,
                "schema": {
                    "name": "check_service_status",
                    "description": "Check operational status of external infrastructure services (e.g. GitHub Status API).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string", "description": "Service name e.g. github"}
                        },
                        "required": []
                    }
                }
            },
            "search_error_kb": {
                "func": search_error_kb,
                "schema": {
                    "name": "search_error_kb",
                    "description": "Search local vector knowledge base (ChromaDB) for matching error symptoms and recommended fixes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "error_text": {"type": "string", "description": "Build error message or symptom text"},
                            "top_k": {"type": "integer", "description": "Max matches to return"}
                        },
                        "required": ["error_text"]
                    }
                }
            },
            "get_past_incidents": {
                "func": get_past_incidents,
                "schema": {
                    "name": "get_past_incidents",
                    "description": "Retrieve past incident records from SQLite database matching component or recent timeline.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "component": {"type": "string", "description": "Optional component name filter"},
                            "limit": {"type": "integer", "description": "Max records to return"}
                        },
                        "required": []
                    }
                }
            },
            "log_new_incident": {
                "func": log_new_incident,
                "schema": {
                    "name": "log_new_incident",
                    "description": "Log a newly diagnosed incident into SQLite database. REQUIRES prior user confirmation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "component": {"type": "string", "description": "Affected component name"},
                            "summary": {"type": "string", "description": "Incident summary"},
                            "root_cause": {"type": "string", "description": "Identified root cause"},
                            "resolution": {"type": "string", "description": "Applied resolution"}
                        },
                        "required": ["component", "summary", "root_cause", "resolution"]
                    }
                }
            }
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return list of available MCP tool schemas dynamically."""
        return [item["schema"] for item in self._tool_registry.values()]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call against the MCP server registry."""
        if tool_name not in self._tool_registry:
            logger.error(f"Requested tool '{tool_name}' not found in MCP registry.")
            return {"error": f"Tool '{tool_name}' is not registered."}

        handler = self._tool_registry[tool_name]["func"]
        try:
            logger.info(f"Executing MCP Tool Call: {tool_name}({arguments})")
            result = handler(**arguments)
            return result
        except Exception as e:
            logger.error(f"Error during MCP tool '{tool_name}' execution: {e}")
            return {"error": f"Tool execution exception: {str(e)}"}
