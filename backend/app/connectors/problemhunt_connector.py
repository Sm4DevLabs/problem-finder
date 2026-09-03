"""
ProblemHunt connector — Crawlviel Tilda CMS extraction.

Uses the deployed Crawlviel API (Tilda Feed adapter) instead of Playwright DOM scraping.
"""

from app.connectors.crawlviel_client import map_cms_item, scrape_extract_all

PROBLEMHUNT_URL = "https://problemhunt.pro"


async def fetch_problems(limit: int | None = None) -> list[dict]:
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
        mapped = map_cms_item(
            item,
            source_key="problemhunt",
            id_prefix="problemhunt",
            fallback_url=PROBLEMHUNT_URL,
        )
        if mapped:
            problems.append(mapped)
        if limit is not None and len(problems) >= limit:
            break

    print(
        f"ProblemHunt: Extracted {len(problems)} problems "
        f"(strategy={data.get('strategy')}, crawlviel_total={data.get('total')})"
    )
    return problems
