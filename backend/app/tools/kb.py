"""Knowledge base search over the support docs."""

from app.rag.store import get_collection

TOP_K = 4
# Chunks with a cosine distance above this are treated as not relevant; if nothing passes,
# the support agent reports no_relevant_info. Measured: relevant hits reached 0.71 (vague
# "my internet is not working"), the closest off-topic hit was 0.78 ("capital of France").
MAX_DISTANCE = 0.75


def search_support_docs(query: str, top_k: int = TOP_K, max_distance: float = MAX_DISTANCE) -> list[dict]:
    """Top matching doc sections, each with its stable ID and source for citation."""
    result = get_collection().query(query_texts=[query], n_results=top_k)
    hits = []
    for chunk_id, text, meta, distance in zip(
        result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        if distance <= max_distance:
            hits.append({
                "chunk_id": chunk_id,
                "source": meta["source"],
                "heading_path": meta["heading_path"],
                "text": text,
                "distance": round(distance, 3),
            })
    return hits
