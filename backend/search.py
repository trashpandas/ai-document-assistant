"""
search.py — Hybrid search: vector similarity + keyword full-text search
========================================================================
Combines pgvector cosine similarity with PostgreSQL full-text search
using Reciprocal Rank Fusion (RRF) for optimal retrieval.
"""

import os
from database import get_connection
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Embedding helper (reuses the model from pdf_pipeline)
# ---------------------------------------------------------------------------

def embed_query(query_text):
    """Embed a single query string. Returns list of 384 floats."""
    from pdf_pipeline import embed_texts
    return embed_texts([query_text])[0]


# ---------------------------------------------------------------------------
# Vector Search
# ---------------------------------------------------------------------------

def vector_search(query_embedding, top_k=20):
    """
    Find the most similar chunks using pgvector cosine distance.
    Returns list of dicts with chunk info and similarity score.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    cur.execute("""
        SELECT
            id, chunk_text, page_number, filename, document_id,
            1 - (embedding <=> %s::vector) as similarity
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """, (emb_str, emb_str, top_k))

    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


# ---------------------------------------------------------------------------
# Keyword (Full-Text) Search
# ---------------------------------------------------------------------------

def keyword_search(query_text, top_k=20):
    """
    Full-text search using PostgreSQL tsvector/tsquery.
    Returns list of dicts with chunk info and relevance rank.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Build a tsquery from the user's natural language query
    # plainto_tsquery handles plain English input gracefully
    cur.execute("""
        SELECT
            id, chunk_text, page_number, filename, document_id,
            ts_rank_cd(to_tsvector('english', chunk_text), plainto_tsquery('english', %s)) as rank
        FROM chunks
        WHERE to_tsvector('english', chunk_text) @@ plainto_tsquery('english', %s)
        ORDER BY rank DESC
        LIMIT %s;
    """, (query_text, query_text, top_k))

    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(vector_results, keyword_results, k=60):
    """
    Combine vector and keyword search results using RRF.
    k is the RRF constant (standard value: 60).
    Returns merged, re-ranked list of results.
    """
    scores = {}  # chunk_id -> { score, data }

    # Score vector results
    for rank, result in enumerate(vector_results):
        chunk_id = result["id"]
        rrf_score = 1.0 / (k + rank + 1)
        if chunk_id not in scores:
            scores[chunk_id] = {"score": 0, "data": result}
        scores[chunk_id]["score"] += rrf_score

    # Score keyword results
    for rank, result in enumerate(keyword_results):
        chunk_id = result["id"]
        rrf_score = 1.0 / (k + rank + 1)
        if chunk_id not in scores:
            scores[chunk_id] = {"score": 0, "data": result}
        scores[chunk_id]["score"] += rrf_score

    # Sort by combined RRF score
    merged = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    return [
        {
            "chunk_id": item["data"]["id"],
            "chunk_text": item["data"]["chunk_text"],
            "page_number": item["data"]["page_number"],
            "filename": item["data"]["filename"],
            "document_id": item["data"]["document_id"],
            "score": item["score"],
        }
        for item in merged
    ]


# ---------------------------------------------------------------------------
# Main Hybrid Search
# ---------------------------------------------------------------------------

def hybrid_search(query_text, top_k=8):
    """
    Run both vector and keyword search, fuse with RRF, return top_k results.

    Returns list of dicts:
    [
        {
            "chunk_text": "...",
            "page_number": 5,
            "filename": "Code of Conduct.pdf",
            "document_id": 1,
            "score": 0.032
        },
        ...
    ]
    """
    print(f"  Search: \"{query_text[:80]}...\"")

    # Generate query embedding
    query_embedding = embed_query(query_text)

    # Run both searches
    vec_results = vector_search(query_embedding, top_k=20)
    kw_results = keyword_search(query_text, top_k=20)

    print(f"    Vector results: {len(vec_results)}, Keyword results: {len(kw_results)}")

    # Fuse results
    fused = reciprocal_rank_fusion(vec_results, kw_results)

    # Return top_k
    top = fused[:top_k]
    print(f"    Returning top {len(top)} chunks")

    return top


def build_context_from_results(search_results):
    """
    Build a context string for Claude's system prompt from search results.
    Groups chunks by document and page for readability.
    """
    if not search_results:
        return "No relevant content found in the uploaded documents."

    # Group by document
    by_doc = {}
    for r in search_results:
        fname = r["filename"]
        if fname not in by_doc:
            by_doc[fname] = []
        by_doc[fname].append(r)

    parts = []
    for fname, chunks in by_doc.items():
        # Sort by page number
        chunks.sort(key=lambda c: c["page_number"])
        doc_parts = [f"--- Document: {fname} ---"]
        for chunk in chunks:
            doc_parts.append(f"[Page {chunk['page_number']}]\n{chunk['chunk_text']}")
        parts.append("\n\n".join(doc_parts))

    return "\n\n".join(parts)
