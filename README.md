# Utopia Discovery Agent

A CLI agent that takes a venture description and returns a structured JSON with market intelligence, five real call targets (≥1 Qatar-based), and a personalised outreach email — replacing manual Investment-team research for Utopia Studio's M2 Discovery module.

---

## Setup

```bash
cd utopia-discovery
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

## How to run

```bash
python agent.py "<venture description>"
```

Output is printed to **stdout** as JSON and saved to `output/<venture-slug>.json`.

## Example command

```bash
python agent.py "B2B SaaS platform helping Qatar logistics companies automate customs documentation and last-mile dispatch coordination, targeting freight forwarders and 3PLs in the GCC."
```

## Model

Defaults to `claude-opus-4-7`. Set `CLAUDE_MODEL=claude-sonnet-4-6` in `.env` for cheaper iteration.

---

## Prompts used

### System prompt (`prompts/system.md`)

Defines the agent's role, the three-part task (market research → call targets → outreach), the exact JSON schema to output, and research guidelines for finding Qatar-based contacts via web search.

Key instructions:
- Use `web_search` to find **real, currently-employed** people — no invented names
- At least 1 of 5 targets must be Qatar/Doha-based
- Outreach must reference specific context (recent news, role change, regulation) — no generic openers
- Return **only** a JSON object in a fenced code block

### User message (constructed in `agent.py`)

The raw venture description string, passed directly as the first user turn. No additional scaffolding — the system prompt carries the full task definition.

---

## APIs called

| API | Purpose |
|-----|---------|
| Anthropic Messages API | Drives the agent loop (`claude-opus-4-7`) |
| Anthropic web_search tool (`web_search_20250305`) | Server-side web search — Claude uses this to find real contacts and market data without a separate search library |

---

## Output schema

```json
{
  "market_brief": {
    "segments": ["..."],
    "pain_points": ["..."],
    "key_players": ["Company: description"]
  },
  "call_targets": [
    {
      "name": "Full Name",
      "company": "Company",
      "role": "Job Title",
      "location": "City, Country",
      "rationale": "Why this person matters"
    }
  ],
  "outreach": {
    "target_name": "Full Name",
    "subject": "Subject line",
    "body": "3–5 sentence email body"
  },
  "qatar_target_count": 1
}
```

See `output/` for a real sample run.

---

## Project structure

```
agent.py          Main CLI script
prompts/
  system.md       System prompt shown to Claude
requirements.txt
.env.example      API key template
output/           Sample run output (committed)
README.md
```
