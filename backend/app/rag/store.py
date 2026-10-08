"""Chroma vector store holding the support doc chunks.

Embeddings use Chroma's built-in all-MiniLM-L6-v2 (ONNX runtime). It is the same local model as
sentence-transformers, without pulling in PyTorch.
"""

import chromadb

from app.config import CHROMA_DIR

COLLECTION = "support_docs"

_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_collection() -> chromadb.Collection:
    # Cosine distance: 0 = same direction, 2 = opposite. Used by the relevance cutoff in kb.py.
    return _get_client().get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def reset_collection() -> None:
    client = _get_client()
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
