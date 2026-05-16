#!/usr/bin/env python3
"""
Utopia Studio Discovery Agent

Researches a venture, finds real call targets (≥1 Qatar-based),
and drafts personalised outreach. Outputs structured JSON.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 8192
MAX_TURNS = 3

PROMPTS_DIR = Path(__file__).parent / "prompts"
OUTPUT_DIR = Path(__file__).parent / "output"


def load_system_prompt() -> str:
    """Load the system prompt from prompts/system.md."""
    path = PROMPTS_DIR / "system.md"
    if not path.exists():
        raise FileNotFoundError(f"System prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def slugify(text: str) -> str:
    """Convert a venture description to a filesystem-safe slug (max 60 chars)."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-")


def extract_json(text: str) -> dict:
    """
    Pull the first JSON object out of a model response.
    Handles both ```json ... ``` fenced blocks and bare JSON.
    """
    # Fenced code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Bare JSON object — find the outermost { }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("No JSON object found in model response.")


def run_agent(client: anthropic.Anthropic, venture: str, system_prompt: str) -> dict:
    """
    Drive the agentic loop.

    Sends the venture description to Claude with the web_search tool enabled.
    Claude performs searches server-side and returns a final JSON response.
    The loop runs up to MAX_TURNS in case the model needs additional prompting.
    """
    messages: list[dict] = [{"role": "user", "content": venture}]

    for turn in range(1, MAX_TURNS + 1):
        print(f"[agent] turn {turn}/{MAX_TURNS} — calling {MODEL} ...", file=sys.stderr)

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        print(f"[agent] stop_reason={response.stop_reason}", file=sys.stderr)

        # Append the full assistant turn to the conversation history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # JSON lives in the last text block; earlier blocks are search calls and preamble
            text_blocks = [b for b in response.content if hasattr(b, "text") and b.text]
            if not text_blocks:
                raise ValueError("Model returned end_turn but no text block found.")
            return extract_json(text_blocks[-1].text)

        elif response.stop_reason == "tool_use":
            # web_search is server-side; we should not normally reach this branch.
            # If we do, acknowledge the tool calls so the loop can continue.
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    print(f"[agent] tool_call: {block.name} — {getattr(block, 'input', {})}", file=sys.stderr)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Search results returned.",
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        else:
            raise RuntimeError(f"Unexpected stop_reason: {response.stop_reason!r}")

    raise RuntimeError(f"Agent did not produce a final response within {MAX_TURNS} turns.")


def validate_output(data: dict) -> None:
    """Warn if the output is missing required fields or Qatar targets."""
    required_top = {"market_brief", "call_targets", "outreach", "qatar_target_count"}
    missing = required_top - data.keys()
    if missing:
        print(f"[warn] Output missing fields: {missing}", file=sys.stderr)

    qatar_count = data.get("qatar_target_count", 0)
    if qatar_count < 1:
        print("[warn] No Qatar-based targets found — outreach strategy is incomplete.", file=sys.stderr)
    else:
        print(f"[agent] Qatar targets: {qatar_count}", file=sys.stderr)

    targets = data.get("call_targets", [])
    if len(targets) < 5:
        print(f"[warn] Only {len(targets)}/5 call targets returned.", file=sys.stderr)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Utopia Discovery Agent — market research + call targets + outreach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Example:\n  python agent.py "B2B SaaS for Qatar logistics..."',
    )
    parser.add_argument(
        "venture",
        nargs="?",
        help="Venture description (or pipe via stdin)",
    )
    args = parser.parse_args()

    # Accept input from arg or stdin
    if args.venture:
        venture = args.venture.strip()
    elif not sys.stdin.isatty():
        venture = sys.stdin.read().strip()
    else:
        parser.print_help()
        sys.exit(1)

    if not venture:
        print("Error: venture description is empty.", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to .env or your environment.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = load_system_prompt()

    print(f"[agent] model={MODEL}", file=sys.stderr)
    print(f"[agent] venture={venture[:80]}{'...' if len(venture) > 80 else ''}", file=sys.stderr)

    result = run_agent(client, venture, system_prompt)

    validate_output(result)

    # Write to output/<slug>.json
    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = slugify(venture)
    output_path = OUTPUT_DIR / f"{slug}.json"
    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    output_path.write_text(output_json, encoding="utf-8")
    print(f"[agent] Written to {output_path}", file=sys.stderr)

    # Print JSON to stdout
    print(output_json)


if __name__ == "__main__":
    main()
