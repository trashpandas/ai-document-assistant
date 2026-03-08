"""
AI Document Assistant — Backend Server (v0.2)
==============================================
A server that:
  1. Serves a web chat interface
  2. Ingests documents (PDF, TXT, MD) — stores both raw and extracted text
  3. Uses Claude to answer questions in a warm, conversational tone
  4. Returns answers with clickable references to document sections
  5. Serves original PDFs for in-app viewing

To run:
    cd backend
    source venv/bin/activate
    export ANTHROPIC_API_KEY="your-key-here"
    python3 server.py

Then open http://localhost:8000 in your browser.
"""

import os
import json
import subprocess
import tempfile
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from pathlib import Path
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
PORT = 8000

# ---------------------------------------------------------------------------
# In-memory document store
# ---------------------------------------------------------------------------
documents = {}       # filename -> extracted text
documents_raw = {}   # filename -> raw bytes (for serving original PDFs)

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


def build_document_context():
    if not documents:
        return "No documents have been uploaded yet."
    parts = []
    for filename, text in documents.items():
        trimmed = text[:16000]
        parts.append(f"--- Document: {filename} ---\n{trimmed}")
    return "\n\n".join(parts)


SYSTEM_PROMPT_TEMPLATE = """You are a friendly, knowledgeable assistant for the Government of Alberta public service.
You answer questions based on uploaded policy documents in a warm, professional, and conversational tone.

IMPORTANT STYLE GUIDELINES:
- Be conversational and approachable — like a helpful colleague, not a textbook.
- Do NOT use markdown formatting (no ##, **, -, or bullet lists). Write in flowing, natural paragraphs.
- When referencing a specific section of a document, include an inline link using this exact format:
  [Section X](ref://FILENAME/section/SECTION_NUMBER)
  For example: [Section 14](ref://Code of Conduct.pdf/section/14)
- Explain concepts in plain language. If the document uses legalistic phrasing, paraphrase it naturally
  and then note the official wording.
- If someone asks about something not covered in the documents, be upfront about it.
  Say something like "I don't see anything about that in the documents I have, but you might want to check with..."
- End responses with a brief, friendly offer to help further when appropriate.

DOCUMENTS:
{context}"""


def extract_text_from_pdf_bytes(pdf_bytes):
    """Extract text from PDF bytes using pdftotext."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        result = subprocess.run(
            ["pdftotext", tmp_path, "-"],
            capture_output=True, text=True
        )
        os.unlink(tmp_path)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        print("  WARNING: pdftotext not found. Install poppler: brew install poppler")
    return None


def extract_text(filename, content):
    """Extract plain text from common file formats."""
    suffix = Path(filename).suffix.lower()

    if suffix in (".txt", ".md", ".csv"):
        return content.decode("utf-8", errors="replace")

    if suffix == ".pdf":
        text = extract_text_from_pdf_bytes(content)
        if text:
            return text
        # Fallback: raw decode (won't be very useful but better than nothing)
        return content.decode("latin-1", errors="replace")

    return content.decode("utf-8", errors="replace")


def parse_multipart(body, boundary):
    """
    Properly parse a multipart/form-data body.
    Returns a list of (filename, file_bytes) tuples.
    """
    results = []
    # Split on boundary
    parts = body.split(b"--" + boundary)

    for part in parts:
        # Skip preamble and epilogue
        if not part or part in (b"--\r\n", b"--", b"\r\n"):
            continue
        if part.startswith(b"--"):
            continue

        # Split headers from body at the double CRLF
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        header_section = part[:header_end].decode("utf-8", errors="replace")
        file_data = part[header_end + 4:]  # skip the \r\n\r\n

        # Remove trailing \r\n that comes before the next boundary
        if file_data.endswith(b"\r\n"):
            file_data = file_data[:-2]

        # Extract filename from Content-Disposition header
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
                self._send_json({"status": "running", "documents_loaded": len(documents)})

        elif path == "/api":
            self._send_json({"status": "running", "documents_loaded": len(documents)})

        elif path == "/documents":
            self._send_json({
                "count": len(documents),
                "documents": [
                    {
                        "filename": n,
                        "characters": len(t),
                        "has_pdf": n in documents_raw,
                    }
                    for n, t in documents.items()
                ],
            })

        elif path.startswith("/pdf/"):
            # Serve original PDF for in-app viewing
            filename = unquote(path[5:])
            if filename in documents_raw:
                self._send_bytes(documents_raw[filename], "application/pdf", filename)
            else:
                self._send_json({"error": "PDF not found"}, 404)

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
            if filename in documents:
                del documents[filename]
                documents_raw.pop(filename, None)
                self._send_json({"message": f"Deleted '{filename}'.", "documents_loaded": len(documents)})
            else:
                self._send_json({"error": "Document not found"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" in content_type:
            # Extract boundary
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

            # Store raw bytes for PDFs so we can serve the original later
            if Path(filename).suffix.lower() == ".pdf":
                documents_raw[filename] = file_data

            # Extract readable text
            text = extract_text(filename, file_data)

            if len(text.strip()) < 10:
                self._send_json({"error": "Could not extract meaningful text from this file. Make sure pdftotext is installed (brew install poppler)."}, 400)
                return

            documents[filename] = text

            print(f"  Uploaded: {filename} ({len(text)} chars extracted, PDF stored: {filename in documents_raw})")

            self._send_json({
                "message": f"Uploaded '{filename}' successfully.",
                "documents_loaded": len(documents),
                "characters_extracted": len(text),
            })

        elif "application/json" in content_type:
            body = json.loads(self._read_body())
            filename = body.get("filename", "document.txt")
            text = body.get("content", "")
            if len(text.strip()) < 10:
                self._send_json({"error": "Content too short"}, 400)
                return
            documents[filename] = text
            self._send_json({
                "message": f"Uploaded '{filename}' successfully.",
                "documents_loaded": len(documents),
                "characters_extracted": len(text),
            })
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

        doc_context = build_document_context()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=doc_context)

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
            sources = [n for n in documents if n.lower() in reply.lower()]
            if not sources and documents:
                sources = list(documents.keys())

            # Build PDF URLs for any documents that have original PDFs stored
            pdf_urls = {}
            for src in sources:
                if src in documents_raw:
                    pdf_urls[src] = f"/pdf/{src}"

            self._send_json({
                "reply": reply,
                "sources": sources,
                "pdf_urls": pdf_urls,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        # Print uploads and errors but suppress routine request logs
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\n  AI Document Assistant v0.2 running on http://localhost:{PORT}")
    print(f"  Open http://localhost:{PORT} in your browser to chat.")
    print(f"  Documents loaded: {len(documents)}")
    print(f"  API key: {'configured' if ANTHROPIC_API_KEY else 'MISSING'}\n")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
