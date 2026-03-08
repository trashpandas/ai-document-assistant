# AI Document Assistant — Setup Guide

A complete AI agent that lets you upload documents and ask questions about them,
powered by Claude. Includes a Python backend server and a native iOS app.

---

## Step 1: Get Your Anthropic API Key

1. Go to **https://console.anthropic.com**
2. Click **Sign Up** (or Sign In if you already have an account)
3. Once logged in, go to **API Keys** in the left sidebar
4. Click **Create Key** and give it a name (e.g., "My AI Agent")
5. Copy the key — it starts with `sk-ant-...`
6. Keep this key private! Never share it or put it in code you publish online.

> **Cost**: Claude API usage is pay-per-use. For a learning project with small
> documents, expect to spend less than $1/month. You'll need to add a payment
> method to your Anthropic account.

---

## Step 2: Set Up the Backend Server

### Install Python (if you don't have it)
- **Mac**: Open Terminal and run: `brew install python3`
  (If you don't have Homebrew: visit https://brew.sh first)
- Or download from: https://www.python.org/downloads/

### Install the dependencies

Open Terminal, navigate to the `backend` folder, and run:

```bash
cd path/to/my-ai-agent/backend
pip3 install -r requirements.txt
```

### Set your API key and start the server

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
python3 server.py
```

You should see:
```
🤖 AI Document Assistant is starting...
   Upload docs:  POST http://localhost:8000/upload
   Ask questions: POST http://localhost:8000/chat
```

### Quick test (optional)

In a new Terminal tab, try uploading a file and asking a question:

```bash
# Upload a document
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/your/document.txt"

# Ask a question
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is this document about?"}'
```

---

## Step 3: Set Up the iOS App

### Prerequisites
- A Mac with **Xcode 15+** installed (free from the Mac App Store)
- An iPhone running iOS 17+ (or use the Xcode Simulator)

### Create the Xcode project

1. Open **Xcode**
2. File → New → Project
3. Choose **iOS → App**
4. Settings:
   - Product Name: `AIAssistant`
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Uncheck "Include Tests" (optional for now)
5. Click **Create** and save wherever you like

### Add the source files

1. In Xcode's file navigator (left panel), delete the default `ContentView.swift`
2. Drag these 4 files from the `ios-app/AIAssistant/` folder into your Xcode project:
   - `AIAssistantApp.swift` (replace the existing one)
   - `APIService.swift`
   - `ChatViewModel.swift`
   - `ChatView.swift`
3. When prompted, check "Copy items if needed"

### Configure the server URL

Open `APIService.swift` and update the `baseURL`:

- **If testing on Simulator** (backend running on the same Mac):
  ```swift
  static let baseURL = "http://localhost:8000"
  ```

- **If testing on a real iPhone** (same Wi-Fi as your Mac):
  ```swift
  static let baseURL = "http://YOUR-MACS-IP:8000"
  ```
  (Find your Mac's IP: System Settings → Wi-Fi → Details → IP Address)

### Allow local network access

Since the backend runs over HTTP (not HTTPS), you need to allow this in the app:

1. In Xcode, click your project name in the navigator
2. Select the **AIAssistant** target
3. Go to the **Info** tab
4. Add a row: `App Transport Security Settings` (Dictionary)
5. Inside it, add: `Allow Arbitrary Loads` = `YES`

### Run the app

1. Make sure your backend server is running (Step 2)
2. Select a simulator or your connected iPhone
3. Press the ▶ Play button (or Cmd+R)
4. The app should launch with a welcome message
5. Tap 📎 to upload a document, then start chatting!

---

## How It All Works

```
┌─────────────┐         ┌──────────────────┐         ┌─────────┐
│   iOS App   │ ──────> │  Python Backend  │ ──────> │  Claude  │
│  (SwiftUI)  │ <────── │   (FastAPI)      │ <────── │   API    │
└─────────────┘  JSON   └──────────────────┘  API    └─────────┘
                              │
                              │ stores
                              ▼
                        ┌──────────┐
                        │ Your     │
                        │ Documents│
                        └──────────┘
```

1. You upload documents through the iOS app (or curl)
2. The backend extracts text and stores it in memory
3. When you ask a question, the backend sends your documents + question to Claude
4. Claude reads the documents and gives you a grounded answer
5. The answer is sent back to the iOS app

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Could not reach the server" | Make sure `python3 server.py` is running |
| "ANTHROPIC_API_KEY not set" | Run `export ANTHROPIC_API_KEY="your-key"` before starting the server |
| App can't connect from real iPhone | Check the IP address and that both devices are on the same Wi-Fi |
| PDF text extraction fails | Install `poppler-utils`: `brew install poppler` |
| Xcode build errors | Make sure you selected iOS 17+ as the deployment target |

---

## Next Steps (When You're Ready)

- **Persistent storage**: Swap the in-memory dict for a database (SQLite, PostgreSQL)
- **Better search**: Add a vector database (ChromaDB) for smarter document retrieval
- **Hosting**: Deploy the backend to a cloud service (Railway, Render, or AWS) so it's always online
- **Authentication**: Add user login so multiple people can use the app securely
- **Streaming**: Use Claude's streaming API for real-time typing effects
