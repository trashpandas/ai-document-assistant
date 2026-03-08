"""
pdf_pipeline.py — PDF processing pipeline using Claude Vision
==============================================================
Splits PDFs into pages, sends each page image to Claude Vision for
structured markdown extraction, then chunks and embeds the text.
"""

import os
import base64
import tempfile
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Chunking parameters
CHUNK_SIZE = 500       # approximate tokens per chunk (~4 chars per token)
CHUNK_OVERLAP = 100    # overlap tokens between consecutive chunks
CHARS_PER_TOKEN = 4    # rough approximation


def _chunk_size_chars():
    return CHUNK_SIZE * CHARS_PER_TOKEN


def _overlap_chars():
    return CHUNK_OVERLAP * CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# PDF → Page Images
# ---------------------------------------------------------------------------

def split_pdf_to_images(pdf_bytes):
    """
    Split PDF bytes into a list of PNG image bytes, one per page.
    Uses pdf2image (which wraps poppler's pdftoppm).
    """
    from pdf2image import convert_from_bytes

    images = convert_from_bytes(pdf_bytes, dpi=200, fmt="png")
    page_images = []
    for img in images:
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        page_images.append(buf.getvalue())

    return page_images


# ---------------------------------------------------------------------------
# Claude Vision — Extract markdown from page image
# ---------------------------------------------------------------------------

VISION_PROMPT = """You are a document extraction specialist. Extract ALL text content from this page image
and format it as clean, well-structured markdown.

RULES:
- Preserve the document's heading hierarchy (use # for main headings, ## for subheadings, etc.)
- Preserve numbered lists, bullet points, and tables
- Preserve bold and italic emphasis where visible
- If there's a page header or footer, include it but mark it as such
- If the page contains a table, format it as a markdown table
- Do NOT add any commentary — just output the extracted markdown
- If the page is blank or contains only decorative elements, output: [blank page]
- Be thorough — capture every word on the page"""


def extract_markdown_from_image(image_bytes):
    """Send a page image to Claude Vision and get structured markdown back."""
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": VISION_PROMPT,
                        },
                    ],
                }
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


# ---------------------------------------------------------------------------
# Text Chunking
# ---------------------------------------------------------------------------

def chunk_text(text, chunk_size_chars=None, overlap_chars=None):
    """
    Split text into overlapping chunks.
    Tries to break at paragraph or sentence boundaries.
    Returns list of chunk strings.
    """
    if chunk_size_chars is None:
        chunk_size_chars = _chunk_size_chars()
    if overlap_chars is None:
        overlap_chars = _overlap_chars()

    if len(text) <= chunk_size_chars:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size_chars

        if end < len(text):
            # Try to break at a paragraph boundary
            para_break = text.rfind("\n\n", start + chunk_size_chars // 2, end + 200)
            if para_break > start:
                end = para_break

            else:
                # Try sentence boundary
                for sep in [". ", ".\n", "! ", "? "]:
                    sent_break = text.rfind(sep, start + chunk_size_chars // 2, end + 100)
                    if sent_break > start:
                        end = sent_break + len(sep)
                        break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward, accounting for overlap
        start = max(start + 1, end - overlap_chars)

    return chunks


# ---------------------------------------------------------------------------
# Embedding Generation
# ---------------------------------------------------------------------------

_embedding_model = None


def get_embedding_model():
    """Lazy-load the sentence-transformers model."""
    global _embedding_model
    if _embedding_model is None:
        print("  Loading embedding model (first time may take a minute)...")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("  Embedding model loaded.")
    return _embedding_model


def embed_texts(texts):
    """
    Generate 384-dimensional embeddings for a list of texts.
    Returns list of lists (each inner list has 384 floats).
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return [emb.tolist() for emb in embeddings]


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

def process_pdf(filename, pdf_bytes, progress_callback=None):
    """
    Full processing pipeline for one PDF:
    1. Split into page images
    2. Extract markdown from each page via Claude Vision
    3. Chunk the text
    4. Generate embeddings
    5. Store everything in the database

    progress_callback(stage, current, total) is called to report progress.

    Returns (doc_id, page_count, total_chunks, total_chars).
    """
    from database import (
        store_document, store_page, store_chunks,
        update_document_markdown
    )

    def report(stage, current=0, total=0):
        if progress_callback:
            progress_callback(stage, current, total)
        print(f"  [{filename}] {stage}" + (f" ({current}/{total})" if total else ""))

    # Step 1: Split PDF into page images
    report("Splitting PDF into pages...")
    page_images = split_pdf_to_images(pdf_bytes)
    page_count = len(page_images)
    report(f"Found {page_count} pages")

    # Store document record
    doc_id = store_document(filename, pdf_bytes, page_count)

    # Step 2: Extract markdown from each page
    all_markdown = []
    for i, img_bytes in enumerate(page_images):
        report("Extracting text with Claude Vision", i + 1, page_count)
        try:
            md = extract_markdown_from_image(img_bytes)
        except Exception as e:
            print(f"  WARNING: Vision extraction failed for page {i+1}: {e}")
            md = f"[extraction failed for page {i+1}]"

        page_id = store_page(doc_id, i + 1, md)
        all_markdown.append((page_id, i + 1, md))

    # Combine all markdown into one document
    full_markdown = "\n\n".join(
        f"--- Page {pn} ---\n{md}" for _, pn, md in all_markdown
    )
    update_document_markdown(doc_id, full_markdown)

    # Step 3: Chunk the text (per page, preserving page numbers)
    report("Chunking text...")
    all_chunks = []  # (page_id, doc_id, chunk_index, chunk_text, page_number, filename)
    chunk_idx = 0

    for page_id, page_num, md in all_markdown:
        if md.strip() and md.strip() != "[blank page]":
            page_chunks = chunk_text(md)
            for ct in page_chunks:
                all_chunks.append((page_id, doc_id, chunk_idx, ct, page_num, filename))
                chunk_idx += 1

    total_chunks = len(all_chunks)
    report(f"Created {total_chunks} chunks")

    # Step 4: Generate embeddings
    if all_chunks:
        report("Generating embeddings...")
        chunk_texts = [c[3] for c in all_chunks]

        # Process in batches of 64 for memory efficiency
        batch_size = 64
        all_embeddings = []
        for batch_start in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[batch_start:batch_start + batch_size]
            batch_embs = embed_texts(batch)
            all_embeddings.extend(batch_embs)
            report("Generating embeddings", min(batch_start + batch_size, len(chunk_texts)), len(chunk_texts))

        # Step 5: Store chunks with embeddings
        report("Storing chunks in database...")
        chunks_for_db = []
        for i, (page_id, doc_id, idx, text, page_num, fname) in enumerate(all_chunks):
            chunks_for_db.append((page_id, doc_id, idx, text, all_embeddings[i], page_num, fname))

        store_chunks(chunks_for_db)

    total_chars = sum(len(md) for _, _, md in all_markdown)
    report(f"Done! {page_count} pages, {total_chunks} chunks, {total_chars} characters")

    return doc_id, page_count, total_chunks, total_chars


# ---------------------------------------------------------------------------
# Simple text file processing (non-PDF)
# ---------------------------------------------------------------------------

def process_text_file(filename, content_bytes):
    """
    Process a plain text, markdown, or CSV file.
    Simpler pipeline — no Vision needed, just chunk and embed.

    Returns (doc_id, 1, total_chunks, total_chars).
    """
    from database import (
        store_document, store_page, store_chunks,
        update_document_markdown
    )

    text = content_bytes.decode("utf-8", errors="replace")
    if len(text.strip()) < 10:
        raise ValueError("File content too short to process.")

    # Store document (no raw PDF for text files)
    doc_id = store_document(filename, b"", 1)

    # Store as single page
    page_id = store_page(doc_id, 1, text, text)
    update_document_markdown(doc_id, text)

    # Chunk
    chunks = chunk_text(text)
    if not chunks:
        return doc_id, 1, 0, len(text)

    # Embed
    print(f"  [{filename}] Generating embeddings for {len(chunks)} chunks...")
    embeddings = embed_texts(chunks)

    # Store
    chunks_for_db = [
        (page_id, doc_id, i, ct, emb, 1, filename)
        for i, (ct, emb) in enumerate(zip(chunks, embeddings))
    ]
    store_chunks(chunks_for_db)

    print(f"  [{filename}] Done! {len(chunks)} chunks, {len(text)} characters")
    return doc_id, 1, len(chunks), len(text)
