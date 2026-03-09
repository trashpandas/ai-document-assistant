"""
database.py — PostgreSQL + pgvector connection and schema management
====================================================================
Handles all database operations for the AI Document Assistant v1.0.
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from datetime import datetime

# ---------------------------------------------------------------------------
# Connection config
# ---------------------------------------------------------------------------
DB_NAME = os.environ.get("DB_NAME", "ai_assistant")
DB_USER = os.environ.get("DB_USER", "")  # defaults to system user
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")


def get_connection():
    """Get a new database connection."""
    conn_params = {"dbname": DB_NAME, "host": DB_HOST, "port": DB_PORT}
    if DB_USER:
        conn_params["user"] = DB_USER
    if DB_PASSWORD:
        conn_params["password"] = DB_PASSWORD
    return psycopg2.connect(**conn_params)


def init_db():
    """Create all tables and extensions if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    # Enable pgvector
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Documents table — stores file-level info and raw PDF bytes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL,
            upload_date TIMESTAMP DEFAULT NOW(),
            page_count INTEGER DEFAULT 0,
            raw_pdf BYTEA,
            full_markdown TEXT DEFAULT ''
        );
    """)

    # Pages table — one row per PDF page with extracted markdown
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            markdown_content TEXT DEFAULT '',
            raw_text TEXT DEFAULT ''
        );
    """)

    # Chunks table — text chunks with vector embeddings for search
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id SERIAL PRIMARY KEY,
            page_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
            document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(384),
            page_number INTEGER DEFAULT 0,
            filename TEXT DEFAULT ''
        );
    """)

    # Full-text search index on chunks
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chunks_fts'
            ) THEN
                CREATE INDEX idx_chunks_fts ON chunks
                    USING GIN (to_tsvector('english', chunk_text));
            END IF;
        END
        $$;
    """)

    # Vector similarity index (IVFFlat — good for small-medium datasets)
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chunks_embedding'
            ) THEN
                CREATE INDEX idx_chunks_embedding ON chunks
                    USING hnsw (embedding vector_cosine_ops);
            END IF;
        END
        $$;
    """)

    # Metadata table — keywords, concepts, contradictions, concerns
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
            meta_type TEXT NOT NULL,
            value TEXT NOT NULL,
            page_references TEXT DEFAULT '[]'
        );
    """)

    # Graph edges — relationships between documents/concepts
    cur.execute("""
        CREATE TABLE IF NOT EXISTS graph_edges (
            id SERIAL PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            source_label TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            target_label TEXT NOT NULL,
            relationship TEXT DEFAULT 'related',
            weight REAL DEFAULT 1.0
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("  Database initialized successfully.")


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------

def store_document(filename, raw_pdf_bytes, page_count=0):
    """Store or update a document record. Returns document ID."""
    conn = get_connection()
    cur = conn.cursor()

    # Upsert — replace if same filename uploaded again
    cur.execute("""
        INSERT INTO documents (filename, raw_pdf, page_count, upload_date)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (filename) DO UPDATE
            SET raw_pdf = EXCLUDED.raw_pdf,
                page_count = EXCLUDED.page_count,
                upload_date = NOW()
        RETURNING id;
    """, (filename, psycopg2.Binary(raw_pdf_bytes), page_count))

    doc_id = cur.fetchone()[0]

    # Clear old pages, chunks, metadata for this document on re-upload
    cur.execute("DELETE FROM pages WHERE document_id = %s;", (doc_id,))
    cur.execute("DELETE FROM chunks WHERE document_id = %s;", (doc_id,))
    cur.execute("DELETE FROM metadata WHERE document_id = %s;", (doc_id,))
    cur.execute("DELETE FROM graph_edges WHERE (source_type = 'document' AND source_id = %s) OR (target_type = 'document' AND target_id = %s);", (doc_id, doc_id))

    conn.commit()
    cur.close()
    conn.close()
    return doc_id


def update_document_markdown(doc_id, full_markdown):
    """Store the combined markdown for the full document."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE documents SET full_markdown = %s WHERE id = %s;", (full_markdown, doc_id))
    conn.commit()
    cur.close()
    conn.close()


def store_page(doc_id, page_number, markdown_content, raw_text=""):
    """Store a single page's extracted content. Returns page ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pages (document_id, page_number, markdown_content, raw_text)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """, (doc_id, page_number, markdown_content, raw_text))
    page_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return page_id


def store_chunks(chunks_data):
    """
    Bulk-insert chunks with embeddings.
    chunks_data: list of (page_id, document_id, chunk_index, chunk_text, embedding_list, page_number, filename)
    """
    if not chunks_data:
        return

    conn = get_connection()
    cur = conn.cursor()

    # Convert embedding lists to pgvector format strings
    values = []
    for page_id, doc_id, idx, text, emb, page_num, fname in chunks_data:
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"
        values.append((page_id, doc_id, idx, text, emb_str, page_num, fname))

    execute_values(cur, """
        INSERT INTO chunks (page_id, document_id, chunk_index, chunk_text, embedding, page_number, filename)
        VALUES %s
    """, values, template="(%s, %s, %s, %s, %s::vector, %s, %s)")

    conn.commit()
    cur.close()
    conn.close()


def store_metadata_items(doc_id, items):
    """
    Bulk-insert metadata items.
    items: list of (meta_type, value, page_references_json_string)
    """
    if not items:
        return

    conn = get_connection()
    cur = conn.cursor()

    values = [(doc_id, mt, val, refs) for mt, val, refs in items]
    execute_values(cur, """
        INSERT INTO metadata (document_id, meta_type, value, page_references)
        VALUES %s
    """, values)

    conn.commit()
    cur.close()
    conn.close()


def store_graph_edges(edges):
    """
    Bulk-insert graph edges.
    edges: list of (source_type, source_id, source_label, target_type, target_id, target_label, relationship, weight)
    """
    if not edges:
        return

    conn = get_connection()
    cur = conn.cursor()

    execute_values(cur, """
        INSERT INTO graph_edges (source_type, source_id, source_label, target_type, target_id, target_label, relationship, weight)
        VALUES %s
    """, edges)

    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------------------------------------------
# Query operations
# ---------------------------------------------------------------------------

def get_all_documents():
    """Return list of all documents with basic info."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, filename, upload_date, page_count,
               LENGTH(full_markdown) as characters,
               (raw_pdf IS NOT NULL) as has_pdf
        FROM documents
        ORDER BY upload_date DESC;
    """)
    docs = cur.fetchall()
    cur.close()
    conn.close()
    return docs


def get_document_pdf(filename):
    """Return raw PDF bytes for a document, or None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT raw_pdf FROM documents WHERE filename = %s;", (filename,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row[0]:
        return bytes(row[0])
    return None


def get_document_markdown(filename):
    """Return the full markdown for a document."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT full_markdown FROM documents WHERE filename = %s;", (filename,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def get_all_metadata():
    """Return all metadata grouped by document."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT m.*, d.filename
        FROM metadata m
        JOIN documents d ON d.id = m.document_id
        ORDER BY d.filename, m.meta_type;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_graph_data():
    """Return all graph nodes and edges for D3.js visualization."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get documents as nodes
    cur.execute("SELECT id, filename, page_count FROM documents;")
    doc_nodes = cur.fetchall()

    # Get unique concepts as nodes
    cur.execute("""
        SELECT DISTINCT value FROM metadata WHERE meta_type = 'concept';
    """)
    concept_nodes = cur.fetchall()

    # Get edges
    cur.execute("SELECT * FROM graph_edges;")
    edges = cur.fetchall()

    cur.close()
    conn.close()

    # Build D3-compatible structure
    nodes = []
    node_index = {}

    for doc in doc_nodes:
        idx = len(nodes)
        node_id = f"doc_{doc['id']}"
        node_index[node_id] = idx
        nodes.append({
            "id": node_id,
            "label": doc["filename"],
            "type": "document",
            "size": max(10, (doc["page_count"] or 1) * 3),
        })

    for concept in concept_nodes:
        idx = len(nodes)
        node_id = f"concept_{concept['value']}"
        if node_id not in node_index:
            node_index[node_id] = idx
            nodes.append({
                "id": node_id,
                "label": concept["value"],
                "type": "concept",
                "size": 8,
            })

    links = []
    for edge in edges:
        source_id = f"{edge['source_type']}_{edge['source_id']}" if edge['source_type'] == 'document' else f"concept_{edge['source_label']}"
        target_id = f"{edge['target_type']}_{edge['target_id']}" if edge['target_type'] == 'document' else f"concept_{edge['target_label']}"

        if source_id in node_index and target_id in node_index:
            links.append({
                "source": source_id,
                "target": target_id,
                "relationship": edge["relationship"],
                "weight": edge["weight"],
            })

    return {"nodes": nodes, "links": links}


def delete_document(filename):
    """Delete a document and all associated data (cascades)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM documents WHERE filename = %s RETURNING id;", (filename,))
    row = cur.fetchone()
    if row:
        doc_id = row[0]
        cur.execute("DELETE FROM graph_edges WHERE (source_type = 'document' AND source_id = %s) OR (target_type = 'document' AND target_id = %s);", (doc_id, doc_id))
    conn.commit()
    cur.close()
    conn.close()
    return row is not None


def document_count():
    """Return total number of documents."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
