"""
ProblemHunt connector — Crawlviel Tilda CMS extraction.

ProblemHunt submissions follow a fixed 5-question template. Crawlviel returns each
submission's answers inline in the item ``text`` field, e.g.::

    1. Describe the problem:
    <answer>
    2. How often does the problem occur?
    <answer>
    3. What attempts have you made to solve the problem?
    <answer>
    4. How much are you willing to pay for the solution?
    <answer>
    5. Problem author:
    <answer>

Answers are frequently left blank by submitters; blanks are filled downstream by
the AI enrichment service. This connector parses whatever the author provided.
"""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.connectors.clients.crawlviel_client import scrape_extract_all

PROBLEMHUNT_URL = "https://problemhunt.pro"

# Ordered (field, question-marker regex) pairs matching the ProblemHunt template.
_QUESTION_MARKERS = [
    ("describe", r"1\.\s*Describe the problem:?"),
    ("frequency", r"2\.\s*How often does the problem occur\??:?"),
    ("attempts", r"3\.\s*What attempts have you made to solve the problem\??:?"),
    ("pricing", r"4\.\s*How much are you willing to pay for the solution\??:?"),
    ("author", r"5\.\s*Problem author:?"),
]


def parse_template_answers(text: str) -> dict[str, str | None]:
    """Split the numbered ProblemHunt template into its five answers."""
    answers: dict[str, str | None] = {key: None for key, _ in _QUESTION_MARKERS}
    if not text:
        return answers

    # Locate each question marker so we can slice the answer that follows it.
    positions = []
    for key, pattern in _QUESTION_MARKERS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            positions.append((match.start(), match.end(), key))
    positions.sort()

    for idx, (_start, end, key) in enumerate(positions):
        next_start = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
        answer = text[end:next_start].strip()
        answers[key] = answer or None

    return answers


def _stable_id(key: str) -> str:
    digest = hashlib.sha256(key.strip().encode("utf-8")).hexdigest()[:20]
    return f"problemhunt-{digest}"


def _map_item(item: dict) -> dict | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None

    item_url = item.get("url") if isinstance(item.get("url"), str) and item["url"].startswith("http") else None
    url = item_url or PROBLEMHUNT_URL
    answers = parse_template_answers(item.get("text") or "")

    # The item title is the problem statement; use the Q1 answer as description when
    # present, otherwise fall back to the title so the record is never empty.
    description = answers["describe"] or title
    # ProblemHunt exposes the submitter's location in the item "description" field.
    author = answers["author"] or (item.get("description") or None)

    return {
        "external_id": _stable_id(item_url or title),
        "title": title[:500],
        "description": description,
        "url": url,
        "problem_frequency": answers["frequency"],
        "existing_solutions": answers["attempts"],
        "pricing_estimate": answers["pricing"],
        "problem_author": author,
        "raw_data": {
            "source": "problemhunt",
            "strategy": "crawlviel",
            "category": item.get("category"),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "host": urlparse(url).netloc,
        },
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch published ProblemHunt problems via Crawlviel.

    Args:
        limit: Optional max items after dedupe (None = all published CMS records)
    """
    try:
        data = await scrape_extract_all(PROBLEMHUNT_URL)
    except Exception as e:
        raise Exception(f"ProblemHunt Crawlviel fetch failed: {e}") from e

    problems: list[dict] = []
    for item in data.get("items") or []:
        mapped = _map_item(item)
        if mapped:
            problems.append(mapped)
        if limit is not None and len(problems) >= limit:
            break

    print(
        f"ProblemHunt: Extracted {len(problems)} problems "
        f"(strategy={data.get('strategy')}, crawlviel_total={data.get('total')})"
    )
    return problems
