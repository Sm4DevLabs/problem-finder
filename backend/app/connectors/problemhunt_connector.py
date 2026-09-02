"""
ProblemHunt connector - Web scraping based collector.

Fetches problems from ProblemHunt.pro using their public pages.
"""

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone


async def fetch_problems(limit: int = 20) -> list[dict]:
    """
    Fetch problems from ProblemHunt.

    Args:
        limit: Maximum number of problems to fetch

    Returns:
        List of problem dictionaries with standardized fields
    """
    problems = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, headers=headers, verify=False
        ) as client:
            # Fetch the main problems page
            response = await client.get("https://problemhunt.pro/problems")

            if response.status_code != 200:
                raise Exception(f"Failed to fetch ProblemHunt: HTTP {response.status_code}")

            soup = BeautifulSoup(response.text, "html.parser")

            # Find problem cards/items (adjust selectors based on actual HTML structure)
            # This is a placeholder - actual selectors need to be determined by inspecting the site
            problem_elements = soup.find_all("div", class_="problem-card", limit=limit)

            if not problem_elements:
                # Try alternative selectors
                problem_elements = soup.find_all("article", limit=limit)

            for idx, elem in enumerate(problem_elements[:limit]):
                try:
                    # Extract problem details (adjust selectors based on actual structure)
                    title_elem = elem.find(["h2", "h3", "h4", "a"])
                    title = title_elem.get_text(strip=True) if title_elem else f"Problem {idx + 1}"

                    desc_elem = elem.find("p") or elem.find("div", class_="description")
                    description = desc_elem.get_text(strip=True) if desc_elem else ""

                    # Try to find URL
                    link_elem = elem.find("a", href=True)
                    url = f"https://problemhunt.pro{link_elem['href']}" if link_elem else None

                    # Try to extract metadata fields
                    frequency = _extract_field(elem, ["frequency", "occurs", "how-often"])
                    solutions = _extract_field(elem, ["solutions", "attempts", "existing"])
                    pricing = _extract_field(elem, ["pricing", "willing-to-pay", "price"])

                    problems.append(
                        {
                            "external_id": f"problemhunt-{idx}-{hash(title)}",
                            "title": title,
                            "description": description,
                            "url": url or "https://problemhunt.pro/problems",
                            "problem_frequency": frequency,
                            "existing_solutions": solutions,
                            "pricing_estimate": pricing,
                            "raw_data": {
                                "source": "problemhunt",
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "html_snippet": str(elem)[:500],
                            },
                        }
                    )
                except Exception as e:
                    print(f"Error parsing problem element: {e}")
                    continue

    except Exception as e:
        raise Exception(f"ProblemHunt fetch failed: {str(e)}")

    return problems


def _extract_field(element, keywords: list[str]) -> str | None:
    """
    Try to extract a field from an element using various keywords.

    Args:
        element: BeautifulSoup element
        keywords: List of possible class names or text patterns

    Returns:
        Extracted text or None
    """
    for keyword in keywords:
        # Try class-based search
        found = element.find(class_=lambda x: x and keyword in x.lower())
        if found:
            return found.get_text(strip=True)

        # Try text-based search
        found = element.find(string=lambda x: x and keyword in x.lower())
        if found:
            parent = found.find_parent()
            if parent:
                return parent.get_text(strip=True)

    return None
