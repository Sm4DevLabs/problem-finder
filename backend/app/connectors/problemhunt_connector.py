"""
ProblemHunt connector - Crawlee+Playwright based collector.

Fetches problems from ProblemHunt.pro which uses dynamic Tilda/JavaScript content.
"""

from crawlee.crawlers import PlaywrightCrawler
from datetime import datetime, timezone
import re


async def fetch_problems(limit: int = 100) -> list[dict]:
    """
    Fetch problems from ProblemHunt using Crawlee+Playwright.

    Args:
        limit: Maximum number of problems to fetch

    Returns:
        List of problem dictionaries with standardized fields
    """
    problems = []

    try:
        crawler = PlaywrightCrawler(
            headless=True,
            max_requests_per_crawl=1,
        )

        @crawler.router.default_handler
        async def handler(context):
            page = context.page

            # Wait for page to fully load
            await page.wait_for_load_state('networkidle', timeout=20000)

            # Wait a bit more for dynamic content
            await page.wait_for_timeout(2000)

            # Get full page text
            full_text = await page.inner_text('body')

            # Parse problems from text
            # ProblemHunt format: Country + Problem description + Date
            # Look for patterns with country indicators
            lines = full_text.split('\n')

            current_problem = None
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Check if this looks like a country/location (often repeated for flag)
                # Countries appear twice (flag + text), followed by problem description
                if i + 2 < len(lines):
                    next_line = lines[i + 1].strip()
                    next_next = lines[i + 2].strip()

                    # If current line equals next line (country repetition) and next_next has content
                    if line == next_line and len(next_next) > 20 and '$' not in line:
                        # This is likely a country marker, next_next is the problem
                        country = line
                        problem_text = next_next

                        # Look for pricing in problem text or following lines
                        pricing = _extract_pricing(problem_text)
                        if not pricing and i + 3 < len(lines):
                            pricing = _extract_pricing(lines[i + 3])

                        # Check for date/badge
                        date_text = None
                        if i + 3 < len(lines) and ('NEW' in lines[i + 3] or re.match(r'[A-Z][a-z]+ \d+', lines[i + 3])):
                            date_text = lines[i + 3]

                        if len(problem_text) > 30:  # Meaningful problem
                            problems.append({
                                "external_id": f"problemhunt-{hash(problem_text)}",
                                "title": problem_text[:200],
                                "description": problem_text,
                                "url": "https://problemhunt.pro/",
                                "problem_frequency": None,
                                "existing_solutions": None,
                                "pricing_estimate": pricing,
                                "raw_data": {
                                    "source": "problemhunt",
                                    "country": country,
                                    "date": date_text,
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                },
                            })

                            if len(problems) >= limit:
                                break

        await crawler.run(['https://problemhunt.pro/'])

        print(f"ProblemHunt: Extracted {len(problems)} problems")

    except Exception as e:
        raise Exception(f"ProblemHunt fetch failed: {str(e)}")

    return problems


def _extract_pricing(text: str) -> str | None:
    """Extract pricing information from text."""
    if not text:
        return None

    # Look for patterns like "$10/month", "$100", "€50", "willing to pay $X"
    pricing_patterns = [
        r'\$\d+(?:[,.]?\d+)?(?:[/\-]\s*(?:month|year|mo|yr|deal))?',
        r'€\d+(?:[,.]?\d+)?(?:[/\-]\s*(?:month|year|mo|yr))?',
        r'₹\d+(?:[,.]?\d+)?(?:[/\-]\s*(?:month|year|mo|yr))?',
        r'£\d+(?:[,.]?\d+)?(?:[/\-]\s*(?:month|year|mo|yr))?',
    ]

    for pattern in pricing_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return None
