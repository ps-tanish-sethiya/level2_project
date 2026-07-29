"""
Live security tools for querying OSV.dev dependency vulnerabilities and package registry information.
"""

import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger("devsentinel.tools.live_security")


def check_dependency_vulnerabilities(package: str, version: str, ecosystem: str = "PyPI") -> Dict[str, Any]:
    """
    Check OSV.dev API for known CVE vulnerabilities for a given package and version.
    
    Args:
        package: Package name e.g. 'pyyaml'
        version: Version string e.g. '5.1'
        ecosystem: Package ecosystem (PyPI, npm, Maven, Go, etc.)
        
    Returns:
        Structured dict with vulnerable (bool), cve_ids (list), severity, summary, and error string.
    """
    url = "https://api.osv.dev/v1/query"
    payload = {
        "package": {
            "name": package,
            "ecosystem": ecosystem
        },
        "version": version
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            
        if response.status_code != 200:
            return {
                "vulnerable": False,
                "cve_ids": [],
                "severity": "NONE",
                "summary": f"OSV API returned status code {response.status_code}",
                "error": f"OSV API HTTP {response.status_code}"
            }
            
        data = response.json()
        vulns = data.get("vulns", [])
        
        if not vulns:
            return {
                "vulnerable": False,
                "cve_ids": [],
                "severity": "NONE",
                "summary": f"No known vulnerabilities found for {package} {version} in OSV database.",
                "error": None
            }
            
        cve_ids = []
        severities = []
        summaries = []
        
        for v in vulns:
            # Extract CVE aliases
            aliases = v.get("aliases", [])
            for alias in aliases:
                if alias.startswith("CVE-") and alias not in cve_ids:
                    cve_ids.append(alias)
            if not cve_ids and v.get("id"):
                cve_ids.append(v["id"])
                
            summaries.append(v.get("summary") or v.get("details", "")[:120])
            
            # Severity mapping if available
            db_severities = v.get("database_specific", {}).get("severity", "")
            if db_severities:
                severities.append(str(db_severities).upper())
                
        severity_label = "HIGH"
        if any("CRITICAL" in s for s in severities):
            severity_label = "CRITICAL"
        elif any("HIGH" in s for s in severities):
            severity_label = "HIGH"
        elif any("MODERATE" in s or "MEDIUM" in s for s in severities):
            severity_label = "MODERATE"
        elif any("LOW" in s for s in severities):
            severity_label = "LOW"
            
        combined_summary = "; ".join(summaries[:3]) if summaries else f"Known vulnerability in {package} {version}"
        
        return {
            "vulnerable": True,
            "cve_ids": cve_ids,
            "severity": severity_label,
            "summary": combined_summary,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error checking OSV vulnerabilities for {package} {version}: {e}")
        return {
            "vulnerable": False,
            "cve_ids": [],
            "severity": "UNKNOWN",
            "summary": f"Failed to check vulnerability status: {str(e)}",
            "error": f"OSV API exception: {str(e)}"
        }


def get_package_info(package: str, ecosystem: str = "pypi") -> Dict[str, Any]:
    """
    Get registry release details for a package from PyPI or npm registry.
    
    Args:
        package: Package name e.g. 'requests'
        ecosystem: Ecosystem name 'pypi' or 'npm'
        
    Returns:
        Structured dict with latest_version, current_release_date, is_deprecated, error.
    """
    eco = ecosystem.lower()
    try:
        with httpx.Client(timeout=10.0) as client:
            if eco == "npm":
                url = f"https://registry.npmjs.org/{package}"
                res = client.get(url)
                if res.status_code != 200:
                    return {
                        "latest_version": "unknown",
                        "current_release_date": "unknown",
                        "is_deprecated": False,
                        "error": f"npm package '{package}' not found or error {res.status_code}"
                    }
                data = res.json()
                dist_tags = data.get("dist-tags", {})
                latest = dist_tags.get("latest", "unknown")
                time_info = data.get("time", {})
                rel_date = time_info.get(latest, time_info.get("modified", "unknown"))
                deprecated = bool(data.get("deprecated", False))
                return {
                    "latest_version": str(latest),
                    "current_release_date": str(rel_date),
                    "is_deprecated": deprecated,
                    "error": None
                }
            else:
                # Default PyPI
                url = f"https://pypi.org/pypi/{package}/json"
                res = client.get(url)
                if res.status_code != 200:
                    return {
                        "latest_version": "unknown",
                        "current_release_date": "unknown",
                        "is_deprecated": False,
                        "error": f"PyPI package '{package}' not found or error {res.status_code}"
                    }
                data = res.json()
                info = data.get("info", {})
                latest = info.get("version", "unknown")
                urls = data.get("urls", [])
                rel_date = urls[0].get("upload_time", "unknown") if urls else "unknown"
                # Check for deprecation keywords in summary
                summary = (info.get("summary") or "").lower()
                is_dep = "deprecated" in summary
                return {
                    "latest_version": str(latest),
                    "current_release_date": str(rel_date),
                    "is_deprecated": is_dep,
                    "error": None
                }
    except Exception as e:
        logger.error(f"Error fetching package info for {package}: {e}")
        return {
            "latest_version": "unknown",
            "current_release_date": "unknown",
            "is_deprecated": False,
            "error": f"Package registry lookup failed: {str(e)}"
        }
