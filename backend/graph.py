"""
graph.py — Knowledge graph builder
====================================
Builds relationship edges between documents and concepts based on
shared metadata (keywords, concepts). Stores edges in the database
for the D3.js visualization.
"""

import json
from database import get_connection, store_graph_edges
from psycopg2.extras import RealDictCursor


def build_graph_for_document(doc_id, metadata_dict, filename=""):
    """
    Build graph edges connecting a document to its concepts,
    and to other documents that share concepts.

    metadata_dict: the result from metadata.extract_metadata()
        {"keywords": [...], "concepts": [...], ...}
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    edges = []

    # 1. Connect document → its concepts
    for concept_entry in metadata_dict.get("concepts", []):
        value = concept_entry.get("value", "") if isinstance(concept_entry, dict) else str(concept_entry)
        if value:
            edges.append((
                "document", doc_id, filename,
                "concept", 0, value,
                "has_concept", 1.0
            ))

    # 2. Connect document → its keywords (lighter weight)
    for kw_entry in metadata_dict.get("keywords", []):
        value = kw_entry.get("value", "") if isinstance(kw_entry, dict) else str(kw_entry)
        if value:
            edges.append((
                "document", doc_id, filename,
                "keyword", 0, value,
                "has_keyword", 0.5
            ))

    # 3. Find other documents that share concepts and create doc-to-doc edges
    cur.execute("""
        SELECT DISTINCT d.id, d.filename, m.value
        FROM metadata m
        JOIN documents d ON d.id = m.document_id
        WHERE m.meta_type = 'concept'
          AND m.document_id != %s
          AND m.value IN (
              SELECT value FROM metadata
              WHERE document_id = %s AND meta_type = 'concept'
          );
    """, (doc_id, doc_id))

    shared = cur.fetchall()

    # Group by target document to calculate weight
    doc_shared_concepts = {}
    for row in shared:
        other_id = row["id"]
        if other_id not in doc_shared_concepts:
            doc_shared_concepts[other_id] = {
                "filename": row["filename"],
                "concepts": []
            }
        doc_shared_concepts[other_id]["concepts"].append(row["value"])

    for other_id, info in doc_shared_concepts.items():
        weight = len(info["concepts"])  # more shared concepts = stronger link
        edges.append((
            "document", doc_id, filename,
            "document", other_id, info["filename"],
            "shares_concepts", float(weight)
        ))

    cur.close()
    conn.close()

    # Store edges
    if edges:
        store_graph_edges(edges)
        print(f"  [{filename}] Graph: {len(edges)} edges created")

    return len(edges)


def rebuild_all_graphs():
    """
    Rebuild the entire knowledge graph from scratch.
    Useful after re-uploading documents or fixing metadata.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Clear existing edges
    cur.execute("DELETE FROM graph_edges;")
    conn.commit()

    # Get all documents with their metadata
    cur.execute("SELECT id, filename FROM documents;")
    docs = cur.fetchall()

    cur.close()
    conn.close()

    from metadata import get_document_metadata

    total_edges = 0
    for doc in docs:
        meta = get_document_metadata(doc["id"])
        count = build_graph_for_document(doc["id"], meta, doc["filename"])
        total_edges += count

    print(f"  Graph rebuilt: {total_edges} total edges across {len(docs)} documents")
    return total_edges
