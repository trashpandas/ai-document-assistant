"""
AI Document Assistant — Backend Server
=======================================
A simple server that:
  1. Serves a web chat interface
  2. Ingests your documents (PDF, TXT, MD)
  3. Uses Claude to answer questions grounded in your documents

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
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
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
documents = {}  # filename -> text content

# ---------------------------------------------------------------------------
# Claude API (using raw HTTP via requests)
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
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": messages,
        },
        timeout=60,
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


def extract_text(filename, content):
    """Extract plain text from common file formats."""
    suffix = Path(filename).suffix.lower()

    if suffix in (".txt", ".md", ".csv"):
        return content.decode("utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            result = subprocess.run(
                ["pdftotext", tmp_path, "-"],
                capture_output=True, text=True
            )
            os.unlink(tmp_path)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except FileNotFoundError:
            pass
        return content.decode("latin-1", errors="replace")

    return content.decode("utf-8", errors="replace")


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
            # Serve the web chat interface
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            try:
                with open(html_path) as f:
                    self._send_html(f.read())
            except FileNotFoundError:
                self._send_json({"status": "running", "documents_loaded": len(documents)})

        elif path == "/documents":
            self._send_json({
                "count": len(documents),
                "documents": [
                    {"filename": n, "characters": len(t)}
                    for n, t in documents.items()
                ],
            })
        elif path == "/api":
            self._send_json({
                "status": "running",
                "documents_loaded": len(documents),
            })
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
            filename = path.replace("/documents/", "", 1)
            from urllib.parse import unquote
            filename = unquote(filename)
            if filename in documents:
                del documents[filename]
                self._send_json({"message": f"Deleted '{filename}'.", "documents_loaded": len(documents)})
            else:
                self._send_json({"error": "Document not found"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" in content_type:
            boundary = content_type.split("boundary=")[-1].encode()
            body = self._read_body()
            parts = body.split(b"--" + boundary)

            for part in parts:
                if b"filename=" in part:
                    header_section, _, file_data = part.partition(b"\r\n\r\n")
                    header_str = header_section.decode("utf-8", errors="replace")
                    filename = "uploaded_file.txt"
                    for segment in header_str.split(";"):
                        if "filename=" in segment:
                            filename = segment.split("=")[-1].strip().strip('"')

                    file_data = file_data.rstrip(b"\r\n--")

                    # Extract text from the file
                    text = extract_text(filename, file_data)
                    documents[filename] = text

                    self._send_json({
                        "message": f"Uploaded '{filename}' successfully.",
                        "documents_loaded": len(documents),
                        "characters_extracted": len(text),
                    })
                    return

            self._send_json({"error": "No file found in upload"}, 400)

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

        system_prompt = f"""You are a helpful assistant that answers questions based on
the following documents. Always ground your answers in the provided documents.
If the answer isn't in the documents, say so honestly.
When you reference information, mention which document it came from.

DOCUMENTS:
{doc_context}"""

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
            self._send_json({"reply": reply, "sources": sources})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\n  AI Document Assistant running on http://localhost:{PORT}")
    print(f"  Open http://localhost:{PORT} in your browser to chat.")
    print(f"  Documents loaded: {len(documents)}")
    print(f"  API key: {'configured' if ANTHROPIC_API_KEY else 'MISSING'}\n")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
