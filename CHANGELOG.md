# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
