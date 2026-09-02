"""
Razorpay Fix My Itch Website connector - Crawlee+Playwright scraper.

Fetches 10,000+ problems from https://razorpay.com/m/fix-my-itch/#all-problems
"""

from crawlee.crawlers import PlaywrightCrawler
from datetime import datetime, timezone
import re


async def fetch_problems(limit: int = 10000) -> list[dict]:
    """
    Fetch problems from Razorpay Fix My Itch website.

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

            # Navigate to all-problems section
            await page.goto('https://razorpay.com/m/fix-my-itch/#all-problems')
            await page.wait_for_load_state('networkidle', timeout=30000)

            # Wait for dynamic content to load
            await page.wait_for_timeout(3000)

            # Scroll aggressively to load ALL problems (lazy loading)
            # Razorpay has 10,000+ problems
            print("Scrolling to load all problems...")
            last_height = 0
            for scroll_attempt in range(100):  # Max 100 scrolls
                # Scroll to bottom
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(800)

                # Check if we reached the bottom
                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    print(f"Reached bottom after {scroll_attempt} scrolls")
                    break
                last_height = new_height

                if scroll_attempt % 10 == 0:
                    print(f"Scrolled {scroll_attempt} times...")

            # Get all text content
            full_text = await page.inner_text('body')

            # Parse problems from text
            # Format: Category\nWhy ... problem text?\n
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]

            # Known categories from Razorpay
            categories = {
                'Housing', 'Healthcare', 'Career', 'Consumer Services', 'Education',
                'Finance', 'Food & Beverage', 'Travel', 'Transportation', 'Real Estate',
                'E-commerce', 'SaaS', 'Logistics', 'Healthtech', 'Edtech', 'Fintech',
                'B2B Services', 'Beauty & Personal Care', 'Home Services', 'Payment Issues'
            }

            i = 0
            while i < len(lines) and len(problems) < limit:
                line = lines[i]

                # Check if this is a category
                if line in categories or line.replace(' ', '').replace('&', '').replace('-', '').lower() in \
                   {cat.replace(' ', '').replace('&', '').replace('-', '').lower() for cat in categories}:

                    category = line

                    # Next line should be the problem (starts with "Why")
                    if i + 1 < len(lines):
                        problem_text = lines[i + 1]

                        # Validate it's a problem (starts with "Why" or is a question)
                        if problem_text.startswith('Why') or '?' in problem_text:
                            # Clean up problem text
                            problem_text = problem_text.strip()

                            # Skip if too short or invalid
                            if len(problem_text) < 20:
                                i += 2
                                continue

                            problems.append({
                                "external_id": f"razorpay-web-{hash(problem_text)}",
                                "title": problem_text[:200],
                                "description": problem_text,
                                "url": f"https://razorpay.com/m/fix-my-itch/#all-problems",
                                "problem_frequency": None,
                                "existing_solutions": None,
                                "pricing_estimate": None,
                                "raw_data": {
                                    "source": "razorpay-website",
                                    "category": category,
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                },
                            })

                            i += 2  # Skip category and problem
                            continue

                i += 1

            print(f"Razorpay Website: Extracted {len(problems)} problems")

        await crawler.run(['https://razorpay.com/m/fix-my-itch/'])

    except Exception as e:
        raise Exception(f"Razorpay website fetch failed: {str(e)}")

    return problems
