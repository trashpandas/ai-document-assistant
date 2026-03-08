# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-08

### Added

- Conversational AI tone — Claude now responds in a warm, professional style instead of raw markdown
- Clickable reference links — inline `[Section X](ref://...)` links in replies open the source document
- PDF viewer modal in web interface for viewing original documents without leaving the chat
- PDF viewer sheet in iOS app using WebKit for native document viewing
- Original PDF preservation — server stores raw PDF bytes alongside extracted text
- New `/pdf/{filename}` endpoint to serve original PDFs for in-app viewing
- `pdf_urls` field in chat API response for client-side link resolution
- App icon (1024x1024) — teal-blue gradient with white question mark, Alberta Wallet style
- Security section in README documenting API key handling

### Changed

- System prompt rewritten for conversational, non-markdown responses with inline citations
- `max_tokens` increased from 1024 to 2048 for more detailed responses
- Chat API response now includes `pdf_urls` alongside `sources`
- Web chat UI now renders HTML-formatted replies with clickable links
- iOS `ChatMessage` model updated to carry `pdfURLs` dictionary
- README updated with new features, architecture diagram, and security notes

### Fixed

- iOS build errors from missing `import Combine`
- Deprecated `onChange(of:perform:)` updated to iOS 17+ syntax

## [0.1.0] - 2026-03-08

### Added

- Python backend server using built-in `http.server` and the Anthropic Claude API
- Web-based chat interface (`index.html`) with responsive design
- Document upload support via web UI (paperclip button) and REST API
- PDF text extraction using `pdftotext` (via poppler)
- Support for TXT, MD, and CSV file uploads
- Multi-turn conversation with history tracking
- Source citation in responses (shows which documents were referenced)
- JSON-based REST API with endpoints for upload, chat, documents list, and delete
- CORS support for cross-origin requests (iOS app, external clients)
- iOS app scaffolding (Swift/SwiftUI) with chat interface and document picker
- Setup guide with step-by-step instructions for backend, web, and iOS
