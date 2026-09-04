"""Razorpay Fix My Itch adapter — Crawlviel Framer CMS, falling back to GitHub."""

from app.connectors.adapters import _razorpay_crawlviel, _razorpay_github


async def fetch(limit: int | None = None) -> list[dict]:
    try:
        problems = await _razorpay_crawlviel.fetch(limit=limit)
        if problems:
            return problems
    except Exception as e:
        print(f"Crawlviel Razorpay adapter failed: {e}, falling back to GitHub adapter")

    return await _razorpay_github.fetch(limit=limit or 20)
