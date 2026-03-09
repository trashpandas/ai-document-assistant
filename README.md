# AI Document Assistant

![Version](https://img.shields.io/badge/version-1.0.1-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-green)
![License](https://img.shields.io/badge/license-GPLv3-orange)
![PostgreSQL](https://img.shields.io/badge/postgresql-16%2B-blue)

A conversational AI assistant that ingests Government of Alberta policy documents (PDF, TXT, MD) and answers questions about them in a warm, professional tone — with smart search, clickable references, and an interactive knowledge graph.
## Screenshots
assets/Screenshot1.png

## What It Does

Upload a PDF and the system will analyze every page using Claude Vision to extract structured markdown, identify keywords and concepts, generate vector embeddings, and build a knowledge graph of relationships. When you ask a question, it uses hybrid search (vector similarity + full-text keyword) to find the most relevant sections, then sends only those sections to Claude for an accurate, grounded answer with page references.

## Architecture

```
┌─────────────┐     ┌──────────────────────────┐     ┌───────────────┐
│  iOS App    │────▶│  Python Backend (v1.0)    │────▶│  Claude API   │
│  (SwiftUI)  │◀────│  http.server + modules    │◀────│  (Sonnet)     │
└─────────────┘     └──────────┬───────────────┘     └───────────────┘
                               │
┌─────────────┐     ┌──────────▼───────────────┐     ┌───────────────┐
│  Web UI     │────▶│  PostgreSQL + pgvector    │     │  Claude Vision│
│  (D3.js)    │◀────│  (documents, chunks,      │     │  (PDF pages)  │
└─────────────┘     │   embeddings, metadata)   │     └───────────────┘
                    └──────────────────────────┘
```

## Features

**Document Processing**
- PDF page-by-page analysis using Claude Vision
- Structured markdown extraction preserving headings, lists, tables
- Automatic text chunking with overlap for search continuity
- Local vector embeddings (sentence-transformers, all-MiniLM-L6-v2)

**Smart Search**
- Hybrid retrieval: vector similarity + PostgreSQL full-text search
- Reciprocal Rank Fusion (RRF) for optimal result merging
- Only the most relevant chunks are sent to Claude (not the whole document)

**Metadata & Knowledge Graph**
- Automated extraction of keywords, concepts, contradictions, and concerns
- Full-page interactive D3.js knowledge graph with dark theme, zoom/pan, and hover highlighting
- Document-to-concept and document-to-document relationship mapping
- Visible connection lines with relationship labels

**Chat Interface**
- Warm, conversational tone (like a helpful colleague)
- Clickable page references that open the original PDF
- Copy and download buttons on every response
- Real-time processing status during document upload

**iOS App**
- Native SwiftUI chat interface
- Document upload via system file picker
- In-app PDF viewer (WebKit)
- Knowledge graph viewer
- Share sheet for exporting responses

## Prerequisites

- macOS with Homebrew
- Python 3.10+
- PostgreSQL 16+ with pgvector extension
- poppler (for PDF processing)
- Anthropic API key

## Quick Start

Install dependencies:

```bash
brew install postgresql@16 pgvector poppler
brew services start postgresql@16
createdb ai_assistant
psql ai_assistant -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Set up Python:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run:

```bash
export ANTHROPIC_API_KEY="your-key-here"
python3 server.py
```

Open http://localhost:8000 in your browser.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web chat interface |
| GET | `/api` | Server status |
| GET | `/documents` | List loaded documents |
| GET | `/documents/status` | Processing status for uploads |
| GET | `/pdf/{filename}` | Serve original PDF |
| GET | `/graph` | Knowledge graph data (JSON) |
| GET | `/graph-view` | Full-page interactive knowledge graph |
| GET | `/metadata` | All document metadata |
| POST | `/upload` | Upload a document (multipart) |
| POST | `/chat` | Send a message |
| DELETE | `/documents/{filename}` | Remove a document |

## Backend Modules

| File | Purpose |
|------|---------|
| `server.py` | HTTP server, routing, request handling |
| `database.py` | PostgreSQL schema, connection, CRUD operations |
| `pdf_pipeline.py` | Claude Vision extraction, chunking, embedding |
| `metadata.py` | Keyword/concept/contradiction/concern extraction |
| `search.py` | Hybrid search with RRF fusion |
| `graph.py` | Knowledge graph edge builder |
| `graph.html` | Full-page D3.js knowledge graph visualization |

## iOS App Structure

| File | Purpose |
|------|---------|
| `CodeofConductAIAssistantApp.swift` | App entry point |
| `ChatView.swift` | Main UI: messages, input, PDF viewer, graph |
| `ChatViewModel.swift` | State management, API calls |
| `APIService.swift` | HTTP client for backend communication |

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.
