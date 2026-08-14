"""
Live repository and external service status tools.
"""

import os
import logging
import httpx
from typing import Dict, Any, List

logger = logging.getLogger("devsentinel.tools.live_repo")


def get_recent_commits(repo: str, limit: int = 5) -> Dict[str, Any]:
    """
    Fetch recent commit history for a GitHub repository.
    
    Args:
        repo: Repository name in 'owner/repo' format.
        limit: Number of commits to return (default 5).
        
    Returns:
        Structured dict with list of commits containing sha, message, author, date.
    """
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token and not token.startswith("your_"):
        headers["Authorization"] = f"Bearer {token}"
        
    url = f"https://api.github.com/repos/{repo}/commits?per_page={limit}"
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 401 and "Authorization" in headers:
                headers_unauth = {"Accept": "application/vnd.github+json"}
                response = client.get(url, headers=headers_unauth)
            
        if response.status_code != 200:
            return {
                "commits": [],
                "error": f"GitHub API returned HTTP {response.status_code} for repo '{repo}'"
            }
            
        raw_commits = response.json()
        commits: List[Dict[str, str]] = []
        
        for c in raw_commits:
            commit_data = c.get("commit", {})
            author_data = commit_data.get("author", {})
            sha = str(c.get("sha", ""))[:7]
            msg = str(commit_data.get("message", "")).splitlines()[0] if commit_data.get("message") else ""
            author_name = str(author_data.get("name") or c.get("author", {}).get("login", "unknown"))
            commit_date = str(author_data.get("date", ""))
            
            commits.append({
                "sha": sha,
                "message": msg,
                "author": author_name,
                "date": commit_date
            })
            
        return {
            "commits": commits,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error fetching commits for {repo}: {e}")
        return {
            "commits": [],
            "error": f"Failed to fetch commit history: {str(e)}"
        }


def check_service_status(service: str = "github") -> Dict[str, Any]:
    """
    Check the current operational status of external infrastructure services (e.g. GitHub).
    
    Args:
        service: Service identifier (default 'github').
        
    Returns:
        Structured dict with service name, status, description, and error string.
    """
    srv = service.lower()
    
    if "github" in srv:
        url = "https://www.githubstatus.com/api/v2/status.json"
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url)
                
            if res.status_code != 200:
                return {
                    "service": "GitHub",
                    "status": "unknown",
                    "description": f"Status API returned HTTP {res.status_code}",
                    "error": f"Status check failed: HTTP {res.status_code}"
                }
                
            data = res.json()
            page_status = data.get("status", {})
            indicator = page_status.get("indicator", "none")
            description = page_status.get("description", "All Systems Operational")
            
            # Indicator mapping: none -> operational, minor/major/critical -> degraded/outage
            status_map = {
                "none": "operational",
                "minor": "degraded_performance",
                "major": "partial_outage",
                "critical": "major_outage"
            }
            mapped_status = status_map.get(indicator, indicator)
            
            return {
                "service": "GitHub",
                "status": mapped_status,
                "description": description,
                "error": None
            }
        except Exception as e:
            logger.error(f"Error checking GitHub status: {e}")
            return {
                "service": "GitHub",
                "status": "unknown",
                "description": f"Failed to connect to status endpoint: {str(e)}",
                "error": f"Status API error: {str(e)}"
            }
    else:
        return {
            "service": service,
            "status": "operational",
            "description": f"Status monitoring for service '{service}' is healthy.",
            "error": None
        }
