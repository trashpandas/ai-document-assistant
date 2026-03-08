# AI Document Assistant

A conversational AI agent that answers questions grounded in your documents. Upload PDFs, text files, or markdown, then ask questions in natural language — the assistant responds using only the content from your documents.

Built with Python and the [Anthropic Claude API](https://docs.anthropic.com).

![Version](https://img.shields.io/badge/version-0.1-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-green)
![License](https://img.shields.io/badge/license-GPLv3-blue)

## Features

- **Document ingestion** — Upload PDF, TXT, MD, and CSV files through the web interface or API
- **Grounded answers** — Claude reads your documents and cites which document each answer comes from
- **Multi-turn conversation** — Ask follow-up questions with full conversation history
- **Web chat interface** — Clean, responsive browser UI with document upload
- **Simple API** — RESTful endpoints for uploading documents and chatting programmatically
- **PDF text extraction** — Automatically extracts text from PDFs using `pdftotext`
- **iOS app ready** — Swift/SwiftUI client included for building a native mobile app

## Quick Start

### Prerequisites

- Python 3.10 or later
- An [Anthropic API key](https://console.anthropic.com)
- `pdftotext` for PDF support (optional): install via `brew install poppler` on macOS

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/ai-document-assistant.git
cd ai-document-assistant/backend

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start the server
python3 server.py
```

Open **http://localhost:8000** in your browser. You should see the chat interface.

### Usage

1. Click the 📎 paperclip button to upload a document
2. Type a question about your document and press Enter
3. The assistant responds with answers grounded in your uploaded content

## API Reference

### `GET /`
Serves the web chat interface.

### `GET /api`
Returns server status.

```json
{ "status": "running", "documents_loaded": 1 }
```

### `GET /documents`
Lists all uploaded documents.

```json
{
  "count": 1,
  "documents": [
    { "filename": "my-doc.pdf", "characters": 16864 }
  ]
}
```

### `POST /upload`
Upload a document to the knowledge base.

**Multipart form upload:**
```bash
curl -X POST http://localhost:8000/upload -F "file=@document.pdf"
```

**JSON upload (pre-extracted text):**
```bash
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{"filename": "doc.txt", "content": "Your document text here..."}'
```

### `POST /chat`
Ask a question about your uploaded documents.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What does the document say about X?"}'
```

**With conversation history:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can you elaborate on that?",
    "conversation_history": [
      {"role": "user", "content": "What is the main topic?"},
      {"role": "assistant", "content": "The main topic is..."}
    ]
  }'
```

### `DELETE /documents/{filename}`
Remove a document from the knowledge base.

```bash
curl -X DELETE http://localhost:8000/documents/my-doc.pdf
```

## Project Structure

```
ai-document-assistant/
├── backend/
│   ├── server.py          # Python backend server (Claude API + document store)
│   ├── index.html          # Web chat interface
│   └── requirements.txt    # Python dependencies
├── ios-app/
│   └── AIAssistant/
│       ├── AIAssistantApp.swift    # App entry point
│       ├── APIService.swift        # Backend API client
│       ├── ChatViewModel.swift     # Chat state management
│       └── ChatView.swift          # SwiftUI chat interface
├── SETUP-GUIDE.md          # Step-by-step setup instructions
├── CHANGELOG.md            # Version history
├── LICENSE                 # MIT License
└── README.md
```

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────┐
│  Web Browser /  │ ──────> │  Python Backend  │ ──────> │  Claude  │
│   iOS App       │ <────── │   (server.py)    │ <────── │   API    │
└─────────────────┘  JSON   └──────────────────┘  HTTP   └─────────┘
                                    │
                                    │ stores text in
                                    ▼
                              ┌──────────┐
                              │ In-Memory│
                              │ Document │
                              │  Store   │
                              └──────────┘
```

1. You upload documents through the web UI (or API)
2. The backend extracts text and stores it in memory
3. When you ask a question, your documents + question are sent to Claude
4. Claude reads the documents and returns a grounded answer
5. The answer (with source citations) is displayed in the UI

## Configuration

| Environment Variable | Required | Description |
|---------------------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key from [console.anthropic.com](https://console.anthropic.com) |

Server settings can be adjusted at the top of `server.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | The Claude model to use |
| `PORT` | `8000` | Server port |
| Document context limit | `16000` chars | Max characters sent per document (in `build_document_context()`) |

## Limitations

- **In-memory storage** — Documents are lost when the server restarts. A database would be needed for persistence.
- **No authentication** — Anyone who can reach the server can use it. Add auth before exposing to a network.
- **Context window** — Very large documents are trimmed to 16,000 characters. For larger collections, a vector database (ChromaDB, Pinecone) would improve retrieval.
- **Single user** — Conversation history is managed client-side. There's no multi-user session management.

## Roadmap

- [ ] Persistent document storage (SQLite)
- [ ] Vector search for smarter document retrieval (ChromaDB)
- [ ] Streaming responses for real-time typing effect
- [ ] User authentication
- [ ] Cloud deployment (Railway, Render, or AWS)
- [ ] Native iOS app build and distribution

## License

This project is licensed under the GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.
