# Changelog

All notable changes to the AI Document Assistant.

## [1.0.1] - 2026-03-08

### Added
- Full-page knowledge graph visualization (graph.html) with dark theme, zoom, pan, and drag
- Visible connection lines between nodes with hover highlighting and relationship labels
- Color-coded legend and node info panel on graph page
- New /graph-view endpoint serving the full-page graph
- PDF reference links now open to the specific page cited (using #page=N)
- "Save Conversation" button downloads entire chat as a text file
- "New Chat" button to start a fresh conversation
- Conversation persistence via localStorage (survives page reloads and tab switches)
- Monochrome SVG toolbar icons with hover tooltips (macOS style)
- Copy and Download icon buttons always visible on assistant messages
- iOS: New Chat button and Save Conversation button in toolbar
- iOS: Save Conversation opens native share sheet for export

### Changed
- Knowledge Graph button now opens in a new browser tab instead of side panel
- Removed D3.js dependency from main chat page (only loaded on graph page)
- iOS Knowledge Graph now opens as full-screen cover instead of half-sheet
- Vector similarity index changed from IVFFlat to HNSW for better small-dataset results
- All toolbar buttons use monochrome line icons instead of text labels

### Fixed
- Search returning incomplete results due to IVFFlat index with too few chunks
- Conversation lost when opening Knowledge Graph or refreshing the page

## [1.0.0] - 2026-03-08

### Added
- PostgreSQL + pgvector database backend (replaces in-memory storage)
- Claude Vision PDF processing — each page analyzed individually for structured markdown extraction
- Local vector embeddings using sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)
- Hybrid search combining vector similarity and PostgreSQL full-text search with Reciprocal Rank Fusion
- Automated metadata extraction: keywords, concepts, contradictions, and concerns per document
- Interactive D3.js force-directed knowledge graph visualization
- Copy and download buttons on assistant messages
- Real-time processing status banner during document upload
- Background document processing (server stays responsive during uploads)
- New API endpoints: /graph, /metadata, /documents/status
- iOS knowledge graph viewer sheet
- iOS context menu with copy and share actions on messages
- iOS processing status banner

### Changed
- Chat now uses hybrid search to find relevant chunks instead of dumping full document text
- System prompt updated to include search results and metadata context
- Web UI completely redesigned with side panels for documents and graph
- iOS timeout increased to 120 seconds for longer processing operations
- DocumentInfo model now includes page count

### Fixed
- Documents larger than 16,000 characters are now fully searchable (no more truncation)

## [0.2.0] - 2026-03-07

### Added
- Professional but warm conversational AI tone
- Clickable document section references (ref:// links)
- In-app PDF viewer using WebKit (web) and WKWebView (iOS)
- Original PDF storage and serving via /pdf/ endpoint
- App icon (1024x1024, teal-blue gradient with white "?")
- DELETE endpoint for removing documents

### Changed
- System prompt rewritten for conversational style (no markdown formatting in responses)
- Chat responses include pdf_urls for source documents

### Fixed
- Multipart form parser rewritten to properly handle PDF binary data
- Claude no longer hallucinates information not present in documents

## [0.1.0] - 2026-03-07

### Added
- Initial release
- Python backend server using http.server
- Document upload (PDF, TXT, MD) with pdftotext extraction
- Claude-powered chat with document context
- Web chat interface
- iOS SwiftUI app with chat, document picker, and document list
- CORS support for cross-origin requests
