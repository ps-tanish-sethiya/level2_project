"""
Local Knowledge Base search tool backed by ChromaDB RAG vector embeddings.
"""

import os
import logging
from typing import Dict, Any, List

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN_WARNING"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import warnings
warnings.filterwarnings("ignore")

logger = logging.getLogger("devsentinel.tools.local_kb")

# Global cached Chroma client & collection to avoid repeated re-instantiation overhead
_chroma_client = None
_collection = None


def _get_collection():
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
        
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        db_path = os.path.join(project_root, "data", "chroma_store")
        
        if not os.path.exists(db_path):
            os.makedirs(db_path, exist_ok=True)
            
        _chroma_client = chromadb.PersistentClient(path=db_path)
        
        # Use sentence-transformers CPU embedding function
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        _collection = _chroma_client.get_or_create_collection(
            name="devsentinel_kb",
            embedding_function=ef
        )
        return _collection
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB collection: {e}")
        return None


def search_error_kb(error_text: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Perform a semantic RAG vector search over the local knowledge base articles in ChromaDB.
    
    Args:
        error_text: Error message, exception snippet, or build failure text.
        top_k: Maximum matches to return (default 3).
        
    Returns:
        Structured dict with list of matches (exceeding similarity threshold >= 0.35),
        each containing title, snippet, recommended_fix, similarity score.
    """
    try:
        top_k = int(top_k)
    except Exception:
        top_k = 3
        
    collection = _get_collection()
    
    if collection is None or collection.count() == 0:
        return {
            "matches": [],
            "error": "Local knowledge base is empty or vector store is uninitialized. Run data/seed_data.py first."
        }
        
    try:
        results = collection.query(
            query_texts=[error_text],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        matches: List[Dict[str, Any]] = []
        
        if results and results.get("documents"):
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            
            for doc, meta, dist in zip(documents, metadatas, distances):
                # Chroma cosine distance range: 0.0 (exact match) to 2.0 (opposite).
                # Convert distance to similarity score: similarity = 1.0 - (dist / 2.0)
                similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                
                # Apply strict similarity threshold of 0.35 as specified in requirements
                if similarity >= 0.35:
                    matches.append({
                        "title": str(meta.get("title", "KB Article")),
                        "snippet": str(meta.get("snippet") or doc[:200]),
                        "recommended_fix": str(meta.get("recommended_fix", "Consult component documentation.")),
                        "similarity": round(float(similarity), 3)
                    })
                    
        return {
            "matches": matches,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error performing Chroma vector query: {e}")
        return {
            "matches": [],
            "error": f"Vector KB search exception: {str(e)}"
        }

# Pre-warm collection on import to eliminate first-query embedding overhead
try:
    import threading
    threading.Thread(target=_get_collection, daemon=True).start()
except Exception:
    pass
