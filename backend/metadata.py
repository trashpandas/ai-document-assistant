"""
metadata.py — Document metadata extraction using Claude
========================================================
Extracts keywords, concepts, contradictions, and concerns from
document markdown, then stores them in the database.
"""

import os
import json
import requests
from database import store_metadata_items, get_connection
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ---------------------------------------------------------------------------
# Metadata extraction prompt
# ---------------------------------------------------------------------------
METADATA_PROMPT = """You are a policy analysis specialist for the Government of Alberta.
Analyze the following document and extract structured metadata.

Return your analysis as a JSON object with exactly these four keys:

{{
  "keywords": [
    {{"value": "keyword or key phrase", "pages": [1, 3, 5]}}
  ],
  "concepts": [
    {{"value": "high-level theme or policy area", "pages": [1, 2]}}
  ],
  "contradictions": [
    {{"value": "description of any internal inconsistency", "pages": [4, 7]}}
  ],
  "concerns": [
    {{"value": "description of anything vague, outdated, or potentially problematic", "pages": [2]}}
  ]
}}

RULES:
- Extract 10-20 keywords (important terms, policy names, role titles)
- Extract 5-10 concepts (broad themes like "conflict of interest", "public trust", "gift policy")
- Only include contradictions if you genuinely find them — it's fine to return an empty list
- Only include concerns if you genuinely find them — it's fine to return an empty list
- Page numbers should reference where the item appears
- Return ONLY the JSON object, no other text
- Make sure it is valid JSON

DOCUMENT:
{document_text}"""


def extract_metadata(doc_id, full_markdown, filename=""):
    """
    Send the document markdown to Claude for metadata extraction.
    Parses the JSON response and stores results in the database.
    Returns the parsed metadata dict.
    """
    # Trim if very long (Claude can handle ~100k tokens but let's be reasonable)
    trimmed = full_markdown[:80000]

    prompt = METADATA_PROMPT.replace("{document_text}", trimmed)

    print(f"  [{filename}] Extracting metadata with Claude...")

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    reply = data["content"][0]["text"]

    # Parse JSON from Claude's response
    # Sometimes Claude wraps it in ```json ... ```, so strip that
    clean = reply.strip()
    if clean.startswith("```"):
        # Remove code fence
        lines = clean.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        clean = "\n".join(lines)

    try:
        metadata = json.loads(clean)
    except json.JSONDecodeError:
        print(f"  WARNING: Could not parse metadata JSON from Claude. Raw response:\n{reply[:500]}")
        metadata = {"keywords": [], "concepts": [], "contradictions": [], "concerns": []}

    # Store in database
    items = []
    for meta_type in ["keywords", "concepts", "contradictions", "concerns"]:
        for entry in metadata.get(meta_type, []):
            value = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            pages = entry.get("pages", []) if isinstance(entry, dict) else []
            items.append((meta_type.rstrip("s"), value, json.dumps(pages)))

    store_metadata_items(doc_id, items)

    counts = {k: len(metadata.get(k, [])) for k in ["keywords", "concepts", "contradictions", "concerns"]}
    print(f"  [{filename}] Metadata extracted: {counts}")

    return metadata


def get_document_metadata(doc_id):
    """Retrieve stored metadata for a document, grouped by type."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT meta_type, value, page_references
        FROM metadata
        WHERE document_id = %s
        ORDER BY meta_type, id;
    """, (doc_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = {"keywords": [], "concepts": [], "contradictions": [], "concerns": []}
    for row in rows:
        mt = row["meta_type"]
        # Map singular back to plural key
        plural = mt + "s" if not mt.endswith("s") else mt
        if plural in result:
            result[plural].append({
                "value": row["value"],
                "pages": json.loads(row["page_references"]) if row["page_references"] else []
            })

    return result
