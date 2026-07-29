"""
Local incident tools for querying and logging past incident history in SQLite database.
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("devsentinel.tools.local_incidents")


def _get_db_connection() -> Optional[sqlite3.Connection]:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db_path = os.path.join(project_root, "data", "incidents.db")
    
    if not os.path.exists(db_path):
        # Create data folder if missing and initialize table
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Ensure schema exists
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        return conn
    except Exception as e:
        logger.error(f"SQLite connection error: {e}")
        return None


def get_past_incidents(component: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Fetch historical incident records from the SQLite database.
    
    Args:
        component: Optional component name filter (e.g. 'auth-service', 'ci/cd').
        limit: Max number of incidents to return (default 5).
        
    Returns:
        Structured dict with list of past incidents containing id, component, summary, root_cause, resolution, date.
    """
    conn = _get_db_connection()
    if conn is None:
        return {
            "incidents": [],
            "error": "Failed to connect to SQLite incidents database."
        }
        
    try:
        with conn:
            cursor = conn.cursor()
            if component:
                cursor.execute("""
                    SELECT id, component, summary, root_cause, resolution, created_at 
                    FROM incidents 
                    WHERE component LIKE ? 
                    ORDER BY id DESC LIMIT ?
                """, (f"%{component}%", limit))
            else:
                cursor.execute("""
                    SELECT id, component, summary, root_cause, resolution, created_at 
                    FROM incidents 
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
                
            rows = cursor.fetchall()
            
        incidents: List[Dict[str, Any]] = []
        for r in rows:
            incidents.append({
                "id": r["id"],
                "component": r["component"],
                "summary": r["summary"],
                "root_cause": r["root_cause"],
                "resolution": r["resolution"],
                "date": str(r["created_at"])
            })
            
        return {
            "incidents": incidents,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error querying incidents database: {e}")
        return {
            "incidents": [],
            "error": f"Database query exception: {str(e)}"
        }
    finally:
        conn.close()


def log_new_incident(component: str, summary: str, root_cause: str, resolution: str) -> Dict[str, Any]:
    """
    Insert a newly diagnosed incident record into the SQLite database.
    
    Args:
        component: Affected subsystem or component.
        summary: Brief summary of the failure.
        root_cause: Detailed root cause diagnosis.
        resolution: Solution or resolution steps applied.
        
    Returns:
        Structured dict with success status, newly created incident_id, and message.
    """
    conn = _get_db_connection()
    if conn is None:
        return {
            "success": False,
            "incident_id": None,
            "message": "Database connection failed",
            "error": "Failed to connect to SQLite incidents database."
        }
        
    try:
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO incidents (component, summary, root_cause, resolution, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (component, summary, root_cause, resolution, created_at))
            incident_id = cursor.lastrowid
            
        return {
            "success": True,
            "incident_id": incident_id,
            "message": f"Successfully logged incident #{incident_id} for component '{component}'.",
            "error": None
        }
    except Exception as e:
        logger.error(f"Error inserting incident into database: {e}")
        return {
            "success": False,
            "incident_id": None,
            "message": f"Failed to log incident: {str(e)}",
            "error": f"Database insert exception: {str(e)}"
        }
    finally:
        conn.close()
