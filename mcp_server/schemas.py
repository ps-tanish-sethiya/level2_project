"""
Pydantic schemas for input parameters and structured responses for DevSentinel MCP tools.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. get_build_status
# ---------------------------------------------------------------------------
class BuildStatusInput(BaseModel):
    repo: str = Field(..., description="Repository name in format 'owner/repo'")
    branch: str = Field("main", description="Branch name to filter build status")


class BuildStatusOutput(BaseModel):
    status: str = Field(..., description="Run status e.g. completed, in_progress, queued")
    conclusion: str = Field(..., description="Run conclusion e.g. success, failure, cancelled")
    run_id: str = Field(..., description="Unique GitHub Actions run ID")
    commit_sha: str = Field(..., description="Associated commit SHA")
    created_at: str = Field(..., description="ISO 8601 timestamp of run creation")
    error: Optional[str] = Field(None, description="Error message if fetch failed")


# ---------------------------------------------------------------------------
# 2. get_build_logs
# ---------------------------------------------------------------------------
class BuildLogsInput(BaseModel):
    repo: str = Field(..., description="Repository name in format 'owner/repo'")
    run_id: str = Field(..., description="GitHub Actions run ID")


class BuildLogsOutput(BaseModel):
    extracted_error: str = Field(..., description="Parsed lines highlighting the primary failure/error")
    raw_log_excerpt: str = Field(..., description="Excerpt of log context around the failure")
    error: Optional[str] = Field(None, description="Error message if log fetch failed")


# ---------------------------------------------------------------------------
# 3. check_dependency_vulnerabilities
# ---------------------------------------------------------------------------
class SecurityVulnerabilityInput(BaseModel):
    package: str = Field(..., description="Package name e.g. pyyaml, requests, lodash")
    version: str = Field(..., description="Package version string e.g. 5.1, 2.25.0")
    ecosystem: str = Field("PyPI", description="Ecosystem name e.g. PyPI, npm, Maven")


class SecurityVulnerabilityOutput(BaseModel):
    vulnerable: bool = Field(..., description="True if known vulnerabilities exist")
    cve_ids: List[str] = Field(default_factory=list, description="List of CVE IDs")
    severity: str = Field("UNKNOWN", description="Highest severity e.g. CRITICAL, HIGH, MODERATE, LOW, NONE")
    summary: str = Field(..., description="Summary description of vulnerabilities")
    error: Optional[str] = Field(None, description="Error message if scan failed")


# ---------------------------------------------------------------------------
# 4. get_package_info
# ---------------------------------------------------------------------------
class PackageInfoInput(BaseModel):
    package: str = Field(..., description="Package name e.g. pyyaml, httpx")
    ecosystem: str = Field("pypi", description="Registry ecosystem e.g. pypi, npm")


class PackageInfoOutput(BaseModel):
    latest_version: str = Field(..., description="Latest available release version")
    current_release_date: str = Field(..., description="Release date of latest version or query info")
    is_deprecated: bool = Field(False, description="True if package is deprecated")
    error: Optional[str] = Field(None, description="Error message if lookup failed")


# ---------------------------------------------------------------------------
# 5. get_recent_commits
# ---------------------------------------------------------------------------
class CommitInfo(BaseModel):
    sha: str = Field(..., description="Commit SHA hash")
    message: str = Field(..., description="Commit message first line")
    author: str = Field(..., description="Author name/username")
    date: str = Field(..., description="Commit timestamp")


class RecentCommitsInput(BaseModel):
    repo: str = Field(..., description="Repository name in format 'owner/repo'")
    limit: int = Field(5, description="Number of recent commits to fetch")


class RecentCommitsOutput(BaseModel):
    commits: List[CommitInfo] = Field(default_factory=list, description="List of recent commits")
    error: Optional[str] = Field(None, description="Error message if fetch failed")


# ---------------------------------------------------------------------------
# 6. check_service_status
# ---------------------------------------------------------------------------
class ServiceStatusInput(BaseModel):
    service: str = Field("github", description="Target service name e.g. github")


class ServiceStatusOutput(BaseModel):
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Operational status e.g. operational, degraded_performance, major_outage")
    description: str = Field(..., description="Status description")
    error: Optional[str] = Field(None, description="Error message if check failed")


# ---------------------------------------------------------------------------
# 7. search_error_kb
# ---------------------------------------------------------------------------
class KBMatch(BaseModel):
    title: str = Field(..., description="KB Article title")
    snippet: str = Field(..., description="Relevant symptom snippet")
    recommended_fix: str = Field(..., description="Recommended resolution steps")
    similarity: float = Field(..., description="Vector search similarity score (0.0 to 1.0)")


class SearchErrorKBInput(BaseModel):
    error_text: str = Field(..., description="Build/runtime error log snippet or description")
    top_k: int = Field(3, description="Maximum number of matches to return")


class SearchErrorKBOutput(BaseModel):
    matches: List[KBMatch] = Field(default_factory=list, description="Matches exceeding similarity threshold (>=0.35)")
    error: Optional[str] = Field(None, description="Error message if search failed")


# ---------------------------------------------------------------------------
# 8. get_past_incidents
# ---------------------------------------------------------------------------
class IncidentRecord(BaseModel):
    id: int = Field(..., description="Incident ID")
    component: str = Field(..., description="Component/service name")
    summary: Optional[str] = Field("", description="Brief incident summary")
    root_cause: str = Field(..., description="Identified root cause")
    resolution: str = Field(..., description="Resolution applied")
    date: str = Field(..., description="Created date ISO string")


class PastIncidentsInput(BaseModel):
    component: Optional[str] = Field(None, description="Optional component name to filter incidents")
    limit: int = Field(5, description="Max incidents to return")


class PastIncidentsOutput(BaseModel):
    incidents: List[IncidentRecord] = Field(default_factory=list, description="List of historical incidents")
    error: Optional[str] = Field(None, description="Error message if query failed")


# ---------------------------------------------------------------------------
# 9. log_new_incident
# ---------------------------------------------------------------------------
class LogIncidentInput(BaseModel):
    component: str = Field(..., description="Component or subsystem affected")
    summary: str = Field(..., description="Brief summary of the incident")
    root_cause: str = Field(..., description="Root cause description")
    resolution: str = Field(..., description="Resolution or fix applied")


class LogIncidentOutput(BaseModel):
    success: bool = Field(..., description="True if incident logged successfully")
    incident_id: Optional[int] = Field(None, description="ID of newly inserted incident")
    message: str = Field(..., description="Result message")
    error: Optional[str] = Field(None, description="Error message if write failed")
