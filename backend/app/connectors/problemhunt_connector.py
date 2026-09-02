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

            # Scroll to load more content
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await page.wait_for_timeout(500)

            # Get full page text
            full_text = await page.inner_text('body')

            # Parse problems from text
            # ProblemHunt format: USA\nUSA\n<problem text>\nNEW or <date>
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]

            # Known countries/regions that appear on ProblemHunt
            common_countries = {
                'USA', 'UK', 'India', 'Russia', 'France', 'Germany', 'Canada',
                'Australia', 'Brazil', 'Argentina', 'Colombia', 'Vietnam', 'Serbia',
                'Georgia', 'Estonia', 'Hungary', 'Greece', 'Morocco', 'Nigeria',
                'Andorra', 'Lebanon', 'Algeria', 'Benin', 'Netherlands'
            }

            i = 0
            while i < len(lines) - 1 and len(problems) < limit:
                line = lines[i]

                # Check if this is a country
                if line in common_countries:
                    country = line

                    # Next line (i+1) should be the problem
                    if i + 1 < len(lines):
                        problem_text = lines[i + 1]

                        # Validate it's a real problem (not a menu item or tag)
                        if len(problem_text) > 40 and \
                           problem_text not in ['Share your problem', 'Join our Telegram community', 'EN'] and \
                           not problem_text.startswith('All') and \
                           not problem_text.startswith('Browse') and \
                           not problem_text.startswith('This website'):

                            # Look for date/badge (i+2)
                            date_text = None
                            if i + 2 < len(lines):
                                potential_date = lines[i + 2]
                                if 'NEW' in potential_date or \
                                   re.match(r'[A-Za-z]+ \d+', potential_date) or \
                                   'Validated' in potential_date:
                                    date_text = potential_date

                            # Extract pricing from problem or nearby text
                            pricing = _extract_pricing(problem_text)
                            if not pricing and i + 2 < len(lines):
                                pricing = _extract_pricing(lines[i + 2])

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

                    i += 2  # Skip country and problem
                    continue

                i += 1

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
