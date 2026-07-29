"""
Utility-based Risk Scoring logic for DevSentinel PR merge safety evaluation.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    risk_level: str = Field(..., description="Overall risk rating: 'LOW', 'MEDIUM', or 'HIGH'")
    numeric_score: int = Field(..., description="Calculated risk score (0-100)")
    is_safe_to_merge: bool = Field(..., description="True if risk is LOW")
    risk_factors: List[str] = Field(default_factory=list, description="List of identified risk factors")
    recommendation: str = Field(..., description="Actionable recommendation for developers")


def calculate_pr_risk(
    build_conclusion: str = "success",
    cve_severity: str = "NONE",
    past_incident_count: int = 0,
    is_external_outage: bool = False
) -> RiskAssessment:
    """
    Calculate PR merge risk score based on build status, dependency vulnerabilities, and past incident history.
    """
    score = 0
    risk_factors = []

    # 1. Build status factor
    conclusion = (build_conclusion or "").lower()
    if conclusion in ("failure", "timed_out", "cancelled"):
        score += 40
        risk_factors.append(f"CI Build Failed ({conclusion.upper()}) [+40 pts]")
    elif conclusion in ("in_progress", "queued"):
        score += 15
        risk_factors.append("CI Build In-Progress/Queued [+15 pts]")
    elif conclusion == "success":
        risk_factors.append("CI Build Succeeded [0 pts]")

    # 2. Dependency CVE severity factor
    sev = (cve_severity or "").upper()
    if sev == "CRITICAL":
        score += 60
        risk_factors.append("Critical Dependency Vulnerability Detected (CVE) [+60 pts]")
    elif sev == "HIGH":
        score += 40
        risk_factors.append("High Severity Vulnerability Detected (CVE) [+40 pts]")
    elif sev in ("MODERATE", "MEDIUM"):
        score += 20
        risk_factors.append("Moderate Severity Vulnerability Detected (CVE) [+20 pts]")
    elif sev == "LOW":
        score += 10
        risk_factors.append("Low Severity Vulnerability Detected (CVE) [+10 pts]")

    # 3. Component past incident frequency factor
    if past_incident_count >= 3:
        score += 30
        risk_factors.append(f"High Component Incident History ({past_incident_count} past incidents) [+30 pts]")
    elif past_incident_count == 2:
        score += 20
        risk_factors.append(f"Moderate Component Incident History ({past_incident_count} past incidents) [+20 pts]")
    elif past_incident_count == 1:
        score += 10
        risk_factors.append("1 Past Incident Recorded on Component [+10 pts]")

    # 4. External Outage Factor adjustment
    if is_external_outage:
        risk_factors.append("Note: Failure attributed to external infrastructure outage, not code changes.")

    # Determine risk level category
    if score < 25:
        level = "LOW"
        safe = True
        rec = "PR is safe to merge. All quality and security checks passed."
    elif score < 50:
        level = "MEDIUM"
        safe = False
        rec = "PR has moderate risk. Require senior developer review before merging."
    else:
        level = "HIGH"
        safe = False
        rec = "DO NOT MERGE. High risk detected due to build failure or security vulnerabilities."

    return RiskAssessment(
        risk_level=level,
        numeric_score=score,
        is_safe_to_merge=safe,
        risk_factors=risk_factors,
        recommendation=rec
    )
