"""
Razorpay Fix My Itch connector — Crawlviel Framer CMS extraction.

Uses the deployed Crawlviel API (Framer `.framercms` adapter).
Published CMS size is the success criterion (~141 curated records), not the
site's cumulative "10,000+" marketing figure.
"""

from app.connectors.crawlviel_client import map_cms_item, scrape_extract_all

RAZORPAY_FIX_MY_ITCH_URL = "https://razorpay.com/m/fix-my-itch/"


async def fetch_problems(limit: int | None = None) -> list[dict]:
    """
    Fetch published Fix My Itch problems via Crawlviel.

    Args:
        limit: Optional max items after dedupe (None = all published CMS records)
    """
    try:
        data = await scrape_extract_all(RAZORPAY_FIX_MY_ITCH_URL)
    except Exception as e:
        raise Exception(f"Razorpay Crawlviel fetch failed: {e}") from e

    problems: list[dict] = []
    for item in data.get("items") or []:
        mapped = map_cms_item(
            item,
            source_key="razorpay-fix-my-itch",
            id_prefix="razorpay-cms",
            fallback_url=RAZORPAY_FIX_MY_ITCH_URL,
        )
        if mapped:
            problems.append(mapped)
        if limit is not None and len(problems) >= limit:
            break

    print(
        f"Razorpay Fix My Itch: Extracted {len(problems)} problems "
        f"(strategy={data.get('strategy')}, crawlviel_total={data.get('total')})"
    )
    return problems
