"""
AI Document Assistant — Backend Server (v1.0)
==============================================
A server that:
  1. Serves a web chat interface with knowledge graph visualization
  2. Ingests documents (PDF, TXT, MD) — processes with Claude Vision,
     extracts metadata, generates embeddings, stores in PostgreSQL
  3. Uses hybrid search (vector + keyword) to find relevant content
  4. Uses Claude to answer questions in a warm, conversational tone
  5. Returns answers with clickable references to document sections
  6. Serves original PDFs for in-app viewing
  7. Provides a knowledge graph API for D3.js visualization

Prerequisites:
    brew install postgresql@16 pgvector poppler
    pip install requests psycopg2-binary sentence-transformers pdf2image Pillow

To run:
    cd backend
    source venv/bin/activate
    export ANTHROPIC_API_KEY="your-key-here"
    python3 server.py

Then open http://localhost:8000 in your browser.
"""

import os
import sys
import json
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from pathlib import Path
import requests

# Local modules
from database import init_db, get_all_documents, get_document_pdf, delete_document, document_count, get_graph_data, get_all_metadata
from pdf_pipeline import process_pdf, process_text_file
from metadata import extract_metadata, get_document_metadata
from search import hybrid_search, build_context_from_results
from graph import build_graph_for_document

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
PORT = 8000

# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------
def call_claude(system_prompt, messages):
    """Call the Anthropic Messages API directly via requests."""
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": messages,
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


SYSTEM_PROMPT_TEMPLATE = """You are a friendly, knowledgeable assistant for the Government of Alberta public service.
You answer questions based on uploaded policy documents in a warm, professional, and conversational tone.

IMPORTANT STYLE GUIDELINES:
- Be conversational and approachable — like a helpful colleague, not a textbook.
- Do NOT use markdown formatting (no ##, **, -, or bullet lists). Write in flowing, natural paragraphs.
- When referencing a specific section or page of a document, include an inline link using this exact format:
  [Section X, Page Y](ref://FILENAME/section/SECTION_NUMBER)
  For example: [Section 14, Page 8](ref://Code of Conduct.pdf/section/14)
- Explain concepts in plain language. If the document uses legalistic phrasing, paraphrase it naturally
  and then note the official wording.
- If someone asks about something not covered in the documents, be upfront about it.
  Say something like "I don't see anything about that in the documents I have, but you might want to check with..."
- End responses with a brief, friendly offer to help further when appropriate.
- ONLY answer based on what is actually written in the documents below. Do NOT invent or assume information.

DOCUMENT CONTEXT (retrieved via search — most relevant sections):
{context}

DOCUMENT METADATA:
{metadata}"""


# ---------------------------------------------------------------------------
# Multipart parser (from v0.2)
# ---------------------------------------------------------------------------
def parse_multipart(body, boundary):
    """
    Properly parse a multipart/form-data body.
    Returns a list of (filename, file_bytes) tuples.
    """
    results = []
    parts = body.split(b"--" + boundary)

    for part in parts:
        if not part or part in (b"--\r\n", b"--", b"\r\n"):
            continue
        if part.startswith(b"--"):
            continue

        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        header_section = part[:header_end].decode("utf-8", errors="replace")
        file_data = part[header_end + 4:]

        if file_data.endswith(b"\r\n"):
            file_data = file_data[:-2]

        filename = None
        for line in header_section.split("\r\n"):
            if "filename=" in line:
                match = re.search(r'filename="([^"]*)"', line)
                if match:
                    filename = match.group(1)

        if filename and file_data:
            results.append((filename, file_data))

    return results


# ---------------------------------------------------------------------------
# Background processing tracker
# ---------------------------------------------------------------------------
processing_status = {}  # filename -> {"status": "processing"|"done"|"error", "message": "..."}


def process_document_background(filename, file_data):
    """Process a document in a background thread."""
    global processing_status
    processing_status[filename] = {"status": "processing", "message": "Starting..."}

    try:
        suffix = Path(filename).suffix.lower()

        if suffix == ".pdf":
            def progress_cb(stage, current=0, total=0):
                msg = stage + (f" ({current}/{total})" if total else "")
                processing_status[filename] = {"status": "processing", "message": msg}

            doc_id, page_count, chunk_count, char_count = process_pdf(
                filename, file_data, progress_callback=progress_cb
            )
        else:
            doc_id, page_count, chunk_count, char_count = process_text_file(filename, file_data)

        # Extract metadata
        processing_status[filename] = {"status": "processing", "message": "Extracting metadata..."}
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT full_markdown FROM documents WHERE id = %s;", (doc_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        full_markdown = row[0] if row else ""
        metadata_result = extract_metadata(doc_id, full_markdown, filename)

        # Build knowledge graph edges
        processing_status[filename] = {"status": "processing", "message": "Building knowledge graph..."}
        build_graph_for_document(doc_id, metadata_result, filename)

        processing_status[filename] = {
            "status": "done",
            "message": f"Processed {page_count} pages, {chunk_count} chunks, {char_count} characters",
            "doc_id": doc_id,
            "page_count": page_count,
            "chunk_count": chunk_count,
            "char_count": char_count,
        }

    except Exception as e:
        print(f"  ERROR processing {filename}: {e}")
        import traceback
        traceback.print_exc()
        processing_status[filename] = {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data, content_type, filename=None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if filename:
            self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    # -- CORS preflight
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # -- GET routes
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            try:
                with open(html_path) as f:
                    self._send_html(f.read())
            except FileNotFoundError:
                self._send_json({"status": "running", "documents_loaded": document_count()})

        elif path == "/api":
            self._send_json({"status": "running", "documents_loaded": document_count()})

        elif path == "/documents":
            docs = get_all_documents()
            self._send_json({
                "count": len(docs),
                "documents": [
                    {
                        "filename": d["filename"],
                        "characters": d["characters"] or 0,
                        "has_pdf": d["has_pdf"],
                        "page_count": d["page_count"] or 0,
                    }
                    for d in docs
                ],
            })

        elif path == "/documents/status":
            self._send_json(processing_status)

        elif path.startswith("/pdf/"):
            filename = unquote(path[5:])
            pdf_data = get_document_pdf(filename)
            if pdf_data:
                self._send_bytes(pdf_data, "application/pdf", filename)
            else:
                self._send_json({"error": "PDF not found"}, 404)

        elif path == "/graph":
            graph_data = get_graph_data()
            self._send_json(graph_data)

        elif path == "/metadata":
            all_meta = get_all_metadata()
            self._send_json({"metadata": [dict(m) for m in all_meta]})

        else:
            self._send_json({"error": "Not found"}, 404)

    # -- POST routes
    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/upload":
            self._handle_upload()
        elif path == "/chat":
            self._handle_chat()
        else:
            self._send_json({"error": "Not found"}, 404)

    # -- DELETE routes
    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/documents/"):
            filename = unquote(path[len("/documents/"):])
            if delete_document(filename):
                processing_status.pop(filename, None)
                self._send_json({"message": f"Deleted '{filename}'.", "documents_loaded": document_count()})
            else:
                self._send_json({"error": "Document not found"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" in content_type:
            boundary = None
            for part in content_type.split(";"):
                part = part.strip()
                if part.startswith("boundary="):
                    boundary = part[9:].strip().encode()
                    break

            if not boundary:
                self._send_json({"error": "No boundary in content type"}, 400)
                return

            body = self._read_body()
            files = parse_multipart(body, boundary)

            if not files:
                self._send_json({"error": "No file found in upload"}, 400)
                return

            filename, file_data = files[0]

            # Start background processing
            thread = threading.Thread(
                target=process_document_background,
                args=(filename, file_data),
                daemon=True
            )
            thread.start()

            self._send_json({
                "message": f"Upload received. Processing '{filename}' in background...",
                "documents_loaded": document_count(),
                "processing": True,
            })

        elif "application/json" in content_type:
            body = json.loads(self._read_body())
            filename = body.get("filename", "document.txt")
            text = body.get("content", "")
            if len(text.strip()) < 10:
                self._send_json({"error": "Content too short"}, 400)
                return

            # Process text directly (quick enough for foreground)
            try:
                doc_id, _, chunk_count, char_count = process_text_file(filename, text.encode("utf-8"))
                self._send_json({
                    "message": f"Uploaded '{filename}' successfully.",
                    "documents_loaded": document_count(),
                    "characters_extracted": char_count,
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self._send_json({"error": "Unsupported content type"}, 400)

    def _handle_chat(self):
        body = json.loads(self._read_body())
        user_message = body.get("message", "")

        if not user_message.strip():
            self._send_json({"error": "Message cannot be empty"}, 400)
            return
        if not ANTHROPIC_API_KEY:
            self._send_json({"error": "API key not configured"}, 500)
            return

        # Hybrid search for relevant chunks
        search_results = hybrid_search(user_message, top_k=8)
        context = build_context_from_results(search_results)

        # Get metadata summary for the system prompt
        all_meta = get_all_metadata()
        meta_summary = ""
        if all_meta:
            by_doc = {}
            for m in all_meta:
                fname = m["filename"]
                if fname not in by_doc:
                    by_doc[fname] = {"concepts": [], "keywords": []}
                if m["meta_type"] == "concept":
                    by_doc[fname]["concepts"].append(m["value"])
                elif m["meta_type"] == "keyword":
                    by_doc[fname]["keywords"].append(m["value"])

            parts = []
            for fname, data in by_doc.items():
                parts.append(f"{fname}: Concepts: {', '.join(data['concepts'][:10])}. Keywords: {', '.join(data['keywords'][:10])}")
            meta_summary = "\n".join(parts)

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            context=context,
            metadata=meta_summary or "No metadata available."
        )

        history = body.get("conversation_history", [])
        messages = []
        for turn in history:
            messages.append({
                "role": turn.get("role", "user"),
                "content": turn.get("content", ""),
            })
        messages.append({"role": "user", "content": user_message})

        try:
            reply = call_claude(system_prompt, messages)

            # Determine source documents from search results
            sources = list(set(r["filename"] for r in search_results))
            if not sources:
                docs = get_all_documents()
                sources = [d["filename"] for d in docs]

            # Build PDF URLs for documents that have stored PDFs
            pdf_urls = {}
            for src in sources:
                pdf_data = get_document_pdf(src)
                if pdf_data:
                    pdf_urls[src] = f"/pdf/{src}"

            self._send_json({
                "reply": reply,
                "sources": sources,
                "pdf_urls": pdf_urls,
                "chunks_used": len(search_results),
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        # Suppress routine request logs
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Initialize database tables
    print("\n  Initializing database...")
    try:
        init_db()
    except Exception as e:
        print(f"\n  ERROR: Could not connect to PostgreSQL: {e}")
        print("  Make sure PostgreSQL is running: brew services start postgresql@16")
        print("  And the database exists: createdb ai_assistant\n")
        sys.exit(1)

    doc_count = document_count()

    print(f"\n  AI Document Assistant v1.0 running on http://localhost:{PORT}")
    print(f"  Open http://localhost:{PORT} in your browser to chat.")
    print(f"  Documents in database: {doc_count}")
    print(f"  API key: {'configured' if ANTHROPIC_API_KEY else 'MISSING'}")
    print(f"  Database: ai_assistant @ localhost:5432\n")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
