# Testing Vitalog with Real Lab Reports

Step-by-step guide for end-to-end testing using your own patient ID and actual lab PDFs.

---

## Part 1 — One-Time Setup

### 1. Generate your patient UUID

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

Save this UUID — you'll use it in every step below.  
Example: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`

---

### 2. Insert a patient row in Supabase

Open **Supabase Dashboard → SQL Editor** and run:

```sql
INSERT INTO patient (patient_id, name, dob)
VALUES (
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  'Your Name',
  '1990-01-01'
);
```

Replace the UUID, name, and date of birth with your own values.  
This row is required — all uploads and records are FK-linked to `patient.patient_id`.

---

### 3. Configure your `.env`

Open `.env` (copy from `.env.example` if it doesn't exist yet):

```bash
cp .env.example .env
```

Fill in all required vars and add your patient ID:

```dotenv
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# AWS (Textract)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...
SUPABASE_DB_URL=postgresql://postgres:...

# Your patient UUID (replaces Mark's hardcoded ID)
VITALOG_PATIENT_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 4. Configure Claude Desktop

Open `~/Library/Application Support/Claude/claude_desktop_config.json` and add the Vitalog MCP server:

```json
{
  "mcpServers": {
    "vitalog": {
      "command": "uv",
      "args": ["run", "python", "scripts/run_mcp_server.py"],
      "cwd": "/Users/sandeepnunna/workspace/100x-Engineers/applications/vitalog",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "...",
        "AWS_REGION": "us-east-1",
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_SERVICE_KEY": "eyJ...",
        "VITALOG_PATIENT_ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    }
  }
}
```

> **Note:** The `env` block is the safest way to pass secrets to Claude Desktop — they stay out of `.env` and are not picked up by other processes.

**Restart Claude Desktop** after saving this file.

---

### 5. Verify the server starts

In Claude Desktop, open a new conversation. You should see "vitalog" listed in the tool panel (hammer icon). If not, check **Settings → Developer → MCP Servers** for error logs.

You can also verify locally:

```bash
cd /Users/sandeepnunna/workspace/100x-Engineers/applications/vitalog
uv run python scripts/run_mcp_server.py
# Should start without errors; exit with Ctrl+C
```

---

## Part 2 — Testing Flow

Use these prompts in Claude Desktop in order. Replace the UUID with your own.

---

### Step 1 — Upload a lab report

Drag your PDF into the Claude Desktop chat or ask Claude to read it from disk, then:

> "Upload this lab report to Vitalog. My patient ID is `a1b2c3d4-e5f6-7890-abcd-ef1234567890`."

Claude will call `upload_document`. Check the response for:
- `category`: should be `lab_report`
- `auto_accepted`: number of biomarkers extracted with high confidence
- `pending_user`: biomarkers that need review
- `pending_taxonomy`: unknown biomarker names (see Troubleshooting)
- `duplicate_skipped`: expected 0 on first upload

Upload a few different lab PDFs (from different dates / labs) to build up history.

---

### Step 2 — List biomarkers

> "List all my biomarkers. My patient ID is `a1b2c3d4-e5f6-7890-abcd-ef1234567890`."

Expected: a table of every biomarker with latest value, unit, date, and record count.

Try filtering:

> "List my glucose-related biomarkers. Patient ID `a1b2c3d4-...`"

---

### Step 3 — View a trend

> "Show me the trend for HbA1c. Patient ID `a1b2c3d4-...`"

Expected: all readings over time with collection dates, values, and guideline bands (e.g. ADA target < 7.0%).

Try other biomarker IDs: `fasting_glucose`, `ldl_cholesterol`, `hdl_cholesterol`, `triglycerides`, `tsh`.

---

### Step 4 — Ask natural language questions

> "What was my last HbA1c result? Patient ID `a1b2c3d4-...`"

> "Do I have any thyroid results? Patient ID `a1b2c3d4-...`"

> "Show me my cholesterol panel from my most recent labs. Patient ID `a1b2c3d4-...`"

Expected: direct answers with values, dates, and source attribution.

---

### Step 5 — Generate a summary

> "Prepare a health summary for patient `a1b2c3d4-...`"

Expected: a structured one-page summary with sections for conditions, key results, trends, and data gaps. The response will include a `summary_id` — save it for the next step.

---

### Step 6 — Export the summary

> "Export that summary as a PDF. Summary ID is `<id from step 5>`, patient ID `a1b2c3d4-...`"

Expected: base64-encoded PDF content. Claude Desktop can decode and display it, or you can decode it locally:

```bash
echo "<base64-string>" | base64 -d > summary.pdf
open summary.pdf
```

Also try markdown and JSON formats:

> "Export summary `<id>` as markdown. Patient ID `a1b2c3d4-...`"

---

## Part 3 — What to Expect

| Scenario | Expected behaviour |
|---|---|
| PDF is a standard Quest/LabCorp report | Textract extracts values; most land in `auto_accepted` |
| PDF is handwritten or low-quality | Vision-LLM fallback kicks in; confidence may be lower |
| Same report uploaded twice | `duplicate_skipped` > 0; no double-counting |
| Non-lab document (insurance card, etc.) | Returns `not_supported`; nothing stored |
| Unknown biomarker name | `pending_taxonomy` > 0; resolve with admin CLI |

---

## Part 4 — Troubleshooting

**"patient_id is not registered"**  
→ The `VITALOG_PATIENT_ID` env var in Claude Desktop's config doesn't match what you're passing to the tool. Double-check both are the same UUID.

**`pending_taxonomy` count is high**  
→ The structurer found biomarker names it can't map to the 30-name taxonomy. Resolve via:
```bash
uv run python scripts/admin.py resolve_pending
```

**Textract errors / no extraction**  
→ Verify AWS credentials are correct and the IAM user has `textract:AnalyzeDocument` permission.

**Claude Desktop doesn't show vitalog tools**  
→ Check `~/Library/Logs/Claude/mcp-server-vitalog.log` for startup errors. Most common cause: wrong `cwd` path or missing env vars.

**Low extraction confidence / many `pending_user`**  
→ The PDF may be a scan or image-only. The vision fallback handles this but confidence is lower. Check `extraction_confidence` values in `list_biomarkers`.
