# v1.0 Setup Walkthrough

Follow these steps one at a time on your Mac. Each step builds on the previous one.

---

## Step 1: Install PostgreSQL

Open Terminal and run:

```
brew install postgresql@16
```

This takes a few minutes. When it finishes, start the PostgreSQL service:

```
brew services start postgresql@16
```

Verify it's running:

```
brew services list
```

You should see `postgresql@16` with status `started`.

---

## Step 2: Add PostgreSQL to your PATH

Run this to make the `psql` command available:

```
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Verify:

```
psql --version
```

Should show something like `psql (PostgreSQL) 16.x`.

---

## Step 3: Create the database

```
createdb ai_assistant
```

Verify it was created:

```
psql ai_assistant -c "SELECT 1;"
```

Should show a row with `1`.

---

## Step 4: Install pgvector extension

```
brew install pgvector
```

Then enable it in your database:

```
psql ai_assistant -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Verify:

```
psql ai_assistant -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Should show `vector`.

---

## Step 5: Update Python dependencies

Navigate to your project and activate the virtual environment:

```
cd ~/ai-agent/backend
source venv/bin/activate
```

Install the new dependencies:

```
pip install psycopg2-binary sentence-transformers pdf2image Pillow
```

This will take a few minutes — `sentence-transformers` downloads the AI embedding model.

**Note:** If you get an error about `poppler`, make sure it's installed:

```
brew install poppler
```

---

## Step 6: Copy the new files

Copy all the new Python files into `~/ai-agent/backend/`:

- `database.py`
- `pdf_pipeline.py`
- `metadata.py`
- `search.py`
- `graph.py`

Replace these existing files:

- `server.py` (completely rewritten for v1.0)
- `index.html` (completely rewritten for v1.0)
- `requirements.txt` (updated with new dependencies)

---

## Step 7: Start the server

Make sure your API key is set and start the server:

```
cd ~/ai-agent/backend
source venv/bin/activate
export ANTHROPIC_API_KEY="your-key-here"
python3 server.py
```

You should see:

```
  Initializing database...
  Database initialized successfully.

  AI Document Assistant v1.0 running on http://localhost:8000
  Open http://localhost:8000 in your browser to chat.
  Documents in database: 0
  API key: configured
  Database: ai_assistant @ localhost:5432
```

---

## Step 8: Test it

Open http://localhost:8000 in your browser and upload the Alberta Code of Conduct PDF.

You'll see a processing banner while the document is being analyzed. This takes 1-2 minutes for the Code of Conduct because each page is sent to Claude Vision for analysis.

Once it's done, try asking a question. Click the "Knowledge Graph" button to see the D3.js visualization.

---

## Step 9: Update iOS app

Copy the updated Swift files into your Xcode project (replace the existing ones):

- `ChatView.swift`
- `ChatViewModel.swift`
- `APIService.swift`
- `CodeofConductAIAssistantApp.swift`

Build and run in Simulator to verify.

---

## Troubleshooting

**"Could not connect to PostgreSQL"**
- Make sure PostgreSQL is running: `brew services start postgresql@16`
- Make sure the database exists: `createdb ai_assistant`

**"pdftotext not found"**
- Install poppler: `brew install poppler`

**"Loading embedding model" takes a long time**
- The first load downloads the model (~80MB). Subsequent starts are instant.

**Server crashes with "lists" error on IVFFlat index**
- This happens if there are fewer rows than the `lists` parameter. Upload at least one document before this matters, and the default of 10 lists is fine for 5-10 documents.
