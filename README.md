# Code of Conduct AI Assistant

A conversational AI agent that answers questions about Government of Alberta policy documents. Upload PDFs or text files, then ask questions in natural language — the assistant responds in a warm, professional tone with clickable references back to the original source documents.

Built with Python and the [Anthropic Claude API](https://docs.anthropic.com).

![Version](https://img.shields.io/badge/version-0.2-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-green)
![License](https://img.shields.io/badge/license-GPLv3-blue)

## Features

- **Conversational AI responses** — Claude answers in a professional but approachable tone, not raw markdown
- **Clickable source references** — Inline links to specific document sections open the original PDF
- **PDF viewer** — View source documents in-app (web modal or iOS WebKit sheet) without leaving the chat
- **Document ingestion** — Upload PDF, TXT, MD, and CSV files through the web interface or API
- **Original PDF preservation** — Stores both extracted text and the original PDF for reference
- **Multi-turn conversation** — Ask follow-up questions with full conversation history
- **Web chat interface** — Clean, responsive browser UI
- **iOS app** — Native SwiftUI chat client with document picker and PDF viewer
- **Simple API** — RESTful endpoints for uploading documents and chatting programmatically

## Quick Start

### Prerequisites

- Python 3.10 or later
- An [Anthropic API key](https://console.anthropic.com)
- `pdftotext` for PDF support: `brew install poppler` on macOS

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/ai-document-assistant.git
cd ai-document-assistant/backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."

python3 server.py
```

Open **http://localhost:8000** in your browser.

### Usage

1. Click the paperclip button to upload a document (PDF, TXT, MD, CSV)
2. Type a question and press Enter
3. The assistant responds conversationally with inline references
4. Click any reference link to view the original document

## API Reference

### `GET /`
Serves the web chat interface.

### `GET /api`
Returns server status and document count.

### `GET /documents`
Lists all uploaded documents with character counts and PDF availability.

### `GET /pdf/{filename}`
Serves the original PDF file for in-app viewing.

### `POST /upload`
Upload a document. Accepts multipart form data or JSON.

```bash
# File upload
curl -X POST http://localhost:8000/upload -F "file=@document.pdf"

# Text upload
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{"filename": "doc.txt", "content": "Your text here..."}'
```

### `POST /chat`
Ask a question. Returns a conversational reply with source references and PDF URLs.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the rules about accepting gifts?"}'
```

Response includes `reply`, `sources`, and `pdf_urls` for linking back to originals.

### `DELETE /documents/{filename}`
Remove a document from the knowledge base.

## Project Structure

```
ai-document-assistant/
├── backend/
│   ├── server.py           # Python backend (Claude API + document store + PDF serving)
│   ├── index.html          # Web chat interface with PDF viewer modal
│   └── requirements.txt    # Python dependencies
├── ios-app/
│   ├── CodeofConductAIAssistantApp.swift   # App entry point
│   ├── APIService.swift                     # Backend API client
│   ├── ChatViewModel.swift                  # Chat state management
│   └── ChatView.swift                       # SwiftUI chat + PDF viewer
├── SETUP-GUIDE.md          # Step-by-step setup instructions
├── CHANGELOG.md            # Version history
├── LICENSE                 # GPLv3 License
└── README.md
```

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────┐
│  Web Browser /  │ ──────> │  Python Backend  │ ──────> │  Claude  │
│   iOS App       │ <────── │   (server.py)    │ <────── │   API    │
└─────────────────┘  JSON   └──────────────────┘  HTTP   └─────────┘
                        │           │
                  PDF viewer    stores text +
                   (modal/      original PDFs
                    WebKit)         │
                              ┌──────────┐
                              │ In-Memory│
                              │ Document │
                              │  Store   │
                              └──────────┘
```

## Configuration

| Environment Variable | Required | Description |
|---------------------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key from [console.anthropic.com](https://console.anthropic.com) |

Server settings in `server.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | The Claude model to use |
| `PORT` | `8000` | Server port |
| Document context limit | `16000` chars | Max characters sent per document |

## Security

The API key is read exclusively from the `ANTHROPIC_API_KEY` environment variable. It is never hardcoded, logged, or transmitted to the client. The `.gitignore` excludes `.env` files and virtual environments.

When deploying, never commit your API key to version control.

## Limitations

- **In-memory storage** — Documents are lost when the server restarts
- **No authentication** — Add auth before exposing to a network
- **Context window** — Very large documents are trimmed to 16,000 characters
- **Local network only** — iOS app requires same Wi-Fi as the backend server

## Roadmap

- [ ] Persistent document storage (SQLite)
- [ ] Vector search for smarter retrieval (ChromaDB)
- [ ] Streaming responses
- [ ] User authentication
- [ ] Cloud deployment
- [ ] TestFlight distribution

## License

This project is licensed under the GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.
