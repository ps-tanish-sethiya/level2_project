"""
Data Seeding Script for DevSentinel.
Initializes SQLite incidents.db with synthetic incident logs and populates ChromaDB vector store with KB embeddings.
"""

import os
import glob
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("devsentinel.seed")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "incidents.db")
KB_DIR = os.path.join(PROJECT_ROOT, "data", "kb")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "data", "chroma_store")

# ---------------------------------------------------------------------------
# Synthetic Past Incidents Seed Data (~15-20 realistic historical incidents)
# ---------------------------------------------------------------------------
SYNTHETIC_INCIDENTS = [
    # 1. Flaky test
    ("ci-pipeline", "Flaky Integration Test Timeout", "Flaky async network request timed out in integration test run", "Increased wait timeout from 5s to 15s in test fixtures"),
    # 2. Dependency CVE
    ("dependencies", "High Severity Vulnerability in PyYAML", "PyYAML 5.1 contained arbitrary code execution CVE-2020-14343", "Upgraded PyYAML to 6.0.1 across requirements.txt"),
    # 3. Missing env var
    ("auth-service", "Authentication Service Startup Crash", "Missing mandatory JWT_SECRET environment variable in staging", "Added default fallback check and updated deployment secrets"),
    # 4. Merge conflict
    ("frontend", "SyntaxError from Git Merge Conflict Marker", "Git merge marker <<<<<<< HEAD accidentally committed to main", "Removed conflict markers and updated git pre-commit hook"),
    # 5. Import typo
    ("payment-gateway", "ModuleNotFoundError in Payment Processing", "Refactored module name without updating import path in handler", "Fixed import path from services.pay to services.payments"),
    # 6. DB timeout
    ("user-db", "Database Connection Pool Exhaustion", "Unclosed SQLite connection handles under high query concurrency", "Wrapped DB connections in context manager blocks"),
    # 7. Rate limit
    ("github-client", "GitHub API Rate Limit Exceeded (HTTP 429)", "Unauthenticated REST calls hit 60 req/hr rate limit ceiling", "Added GITHUB_TOKEN bearer header and retry backoff"),
    # 8. Permission denied
    ("ci-runner", "Permission Denied executing deploy script", "Deploy shell script lacked +x POSIX execution bit in git index", "Updated git file mode via git update-index --chmod=+x"),
    # 9. Null pointer
    ("order-service", "AttributeError NoneType object has no attribute get", "Optional API payload field was null and dereferenced directly", "Added defensive None checks and Pydantic field validation"),
    # 10. Test ordering
    ("test-suite", "Intermittent Test Pollution Failure", "Test case modified shared global state without resetting in teardown", "Added autouse cleanup fixture to reset global state"),
    # 11. Memory leak
    ("worker-node", "Background Worker OOMKilled", "Unbounded in-memory list cache accumulated expired event logs", "Implemented bounded LRU cache with maxsize=1000"),
    # 12. SSL expired
    ("metrics-collector", "SSL Certificate Verification Failed", "Third-party telemetry endpoint certificate expired", "Updated certifi package and renewed server SSL certificate"),
    # 13. Additional synthetic incidents for historical coverage
    ("redis-cache", "Redis Cache Connection Timeout", "Transient network jitter between worker and Redis node", "Added automatic reconnection retry policy"),
    # 14
    ("auth-service", "OAuth Callback Invalid State Token", "Clock drift across auth cluster nodes caused state token mismatch", "Configured chrony NTP daemon across cluster nodes"),
    # 15
    ("ci-pipeline", "Pytest Collection Failure on Missing Fixture", "Renamed fixture name in conftest.py breaking dependent modules", "Updated fixture imports in test module headers"),
    # 16
    ("docker-build", "Docker Layer Caching Invalidation Failure", "Unpinned base image pulled breaking upstream update", "Pinned Dockerfile FROM image to specific digest hash"),
    # 17
    ("api-gateway", "CORS Preflight Request Blocked", "Missing Access-Control-Allow-Origin header on error responses", "Updated CORS middleware to handle 500 error responses"),
]


def seed_sqlite():
    logger.info(f"Initializing SQLite database at: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            conn.execute("DROP TABLE IF EXISTS incidents")
            conn.execute("""
                CREATE TABLE incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            for comp, summ, cause, res in SYNTHETIC_INCIDENTS:
                conn.execute("""
                    INSERT INTO incidents (component, summary, root_cause, resolution)
                    VALUES (?, ?, ?, ?)
                """, (comp, summ, cause, res))
                
        logger.info(f"Successfully seeded SQLite incidents table with {len(SYNTHETIC_INCIDENTS)} records.")
    except Exception as e:
        logger.error(f"Failed to seed SQLite database: {e}")
        raise
    finally:
        conn.close()


def seed_chroma():
    logger.info(f"Indexing KB markdown articles into ChromaDB vector store at: {CHROMA_DIR}")
    os.makedirs(CHROMA_DIR, exist_ok=True)
    
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        
        try:
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        except Exception as dl_err:
            logger.error("=" * 60)
            logger.error(f"CRITICAL: SentenceTransformer model download failed: {dl_err}")
            logger.error("Please check your internet connection and re-run python data/seed_data.py")
            logger.error("=" * 60)
            return
            
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        
        # Reset or recreate collection
        try:
            client.delete_collection("devsentinel_kb")
        except Exception:
            pass
            
        collection = client.create_collection(
            name="devsentinel_kb",
            embedding_function=ef
        )
        
        kb_files = glob.glob(os.path.join(KB_DIR, "*.md"))
        if not kb_files:
            logger.warning(f"No markdown files found in {KB_DIR}")
            return
            
        documents = []
        metadatas = []
        ids = []
        
        for file_path in kb_files:
            filename = os.path.basename(file_path)
            doc_id = os.path.splitext(filename)[0]
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Parse sections: Title, Symptom, Recommended Fix
            lines = content.splitlines()
            title = lines[0].replace("#", "").strip() if lines else doc_id
            
            symptom_snippet = ""
            fix_snippet = ""
            
            if "## Symptom" in content and "## Recommended Fix" in content:
                try:
                    symptom_part = content.split("## Symptom")[1].split("## Root Cause")[0].strip()
                    symptom_snippet = symptom_part
                except Exception:
                    symptom_snippet = content[:300]
                    
                try:
                    fix_part = content.split("## Recommended Fix")[1].strip()
                    fix_snippet = fix_part
                except Exception:
                    fix_snippet = "Consult KB article documentation."
            else:
                symptom_snippet = content[:300]
                fix_snippet = "Consult KB article documentation."
                
            documents.append(content)
            metadatas.append({
                "title": title,
                "filename": filename,
                "snippet": symptom_snippet[:250],
                "recommended_fix": fix_snippet[:250]
            })
            ids.append(doc_id)
            
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Successfully indexed {len(documents)} KB articles into ChromaDB.")
    except Exception as e:
        logger.error(f"Error seeding ChromaDB: {e}")
        logger.error("Continuing without failing script execution.")


if __name__ == "__main__":
    logger.info("=== Starting DevSentinel Local Data Seeding ===")
    seed_sqlite()
    seed_chroma()
    logger.info("=== Data Seeding Complete ===")
