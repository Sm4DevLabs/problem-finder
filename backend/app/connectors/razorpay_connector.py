"""
Razorpay Fix My Itch connector - GitHub API based collector.

Fetches problems from razorpay-fix-my-itch GitHub organization.
Uses AI to enrich problems with missing fields.
"""

import httpx
import ollama
from datetime import datetime, timezone

from app.database.database_session import settings


async def fetch_problems(limit: int = 20) -> list[dict]:
    """
    Fetch problems from Razorpay Fix My Itch GitHub organization.

    Args:
        limit: Maximum number of problems to fetch

    Returns:
        List of problem dictionaries with AI-enriched fields
    """
    problems = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch repositories from razorpay-fix-my-itch organization
            response = await client.get(
                "https://api.github.com/orgs/razorpay-fix-my-itch/repos",
                params={"per_page": limit, "sort": "updated", "direction": "desc"},
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "ProblemFinder",
                },
            )

            if response.status_code != 200:
                raise Exception(f"GitHub API error: HTTP {response.status_code}")

            repos = response.json()

            for repo in repos[:limit]:
                try:
                    # Fetch README for detailed problem description
                    readme_content = await _fetch_readme(client, repo["full_name"])

                    # Build problem from repo data
                    problem_data = {
                        "repo_name": repo["name"],
                        "description": repo["description"] or "",
                        "readme": readme_content,
                        "stars": repo["stargazers_count"],
                        "forks": repo["forks_count"],
                        "topics": repo.get("topics", []),
                        "url": repo["html_url"],
                    }

                    # Use AI to enrich with missing fields
                    enriched = await _enrich_with_ai(problem_data)

                    # Skip if not software-solvable
                    if enriched is None:
                        continue

                    problems.append(
                        {
                            "external_id": repo["full_name"],
                            "title": _clean_title(repo["name"]),
                            "description": enriched["description"],
                            "url": repo["html_url"],
                            "problem_frequency": enriched["problem_frequency"],
                            "existing_solutions": enriched["existing_solutions"],
                            "pricing_estimate": enriched["pricing_estimate"],
                            "tech_stack_options": enriched.get("tech_stack_options"),
                            "recommended_tech_stack": enriched.get("recommended_tech_stack"),
                            "tech_stack_justification": enriched.get("tech_stack_justification"),
                            "raw_data": {
                                "source": "razorpay-fix-my-itch",
                                "repo_data": problem_data,
                                "fetched_at": datetime.now(timezone.utc).isoformat(),
                            },
                        }
                    )

                except Exception as e:
                    print(f"Error processing repo {repo.get('name', 'unknown')}: {e}")
                    continue

    except Exception as e:
        raise Exception(f"Razorpay fetch failed: {str(e)}")

    return problems


async def _fetch_readme(client: httpx.AsyncClient, repo_full_name: str) -> str:
    """Fetch README content for a repository."""
    try:
        response = await client.get(
            f"https://api.github.com/repos/{repo_full_name}/readme",
            headers={
                "Accept": "application/vnd.github.v3.raw",
                "User-Agent": "ProblemFinder",
            },
        )

        if response.status_code == 200:
            return response.text[:2000]  # Limit to 2000 chars
        return ""

    except Exception:
        return ""


async def _enrich_with_ai(problem_data: dict) -> dict:
    """
    Use Ollama AI to enrich problem with missing fields.

    Args:
        problem_data: Raw problem data from GitHub

    Returns:
        Dictionary with enriched fields
    """
    prompt = f"""Analyze this problem and determine if it can be solved with software (app, web app, extension, SaaS, mobile app, etc.).

**Problem Title:** {problem_data['repo_name']}
**Description:** {problem_data['description']}
**README Excerpt:** {problem_data['readme'][:1000]}
**Topics:** {', '.join(problem_data['topics'])}

IMPORTANT: If this problem CANNOT be solved with software/apps/digital solutions (e.g., physical product, offline service, hardware-only), respond with:
{{
  "is_software_solvable": false,
  "reason": "why this is not solvable with software"
}}

If it CAN be solved with software, provide:

1. **Enhanced Description** (2-3 sentences summarizing the problem clearly)
2. **Problem Frequency** (How often does this problem occur? Daily, weekly, or specific scenarios)
3. **Existing Solutions** (What current tools/apps try to solve this? What are their limitations?)
4. **Pricing Estimate** (How much could users be charged for this solution? Consider market, complexity, value)
5. **Tech Stack Options** (List 3-4 possible tech stack combinations with their pros/cons)
6. **Recommended Tech Stack** (Pick the best option from above)
7. **Tech Stack Justification** (Why is the recommended stack the best choice?)

Respond ONLY with valid JSON:
{{
  "is_software_solvable": true,
  "description": "clear 2-3 sentence problem summary",
  "problem_frequency": "frequency analysis",
  "existing_solutions": "analysis of existing solutions and gaps",
  "pricing_estimate": "pricing recommendation with rationale",
  "tech_stack_options": [
    {{"name": "Stack 1", "technologies": ["React", "Node.js", "PostgreSQL"], "pros": "...", "cons": "..."}},
    {{"name": "Stack 2", "technologies": ["Vue", "Python", "MongoDB"], "pros": "...", "cons": "..."}}
  ],
  "recommended_tech_stack": {{"name": "Stack 1", "technologies": ["React", "Node.js", "PostgreSQL"]}},
  "tech_stack_justification": "why this stack is best for this problem"
}}

Be concise and practical. Focus on software-solvable problems only."""

    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )

        import json

        enriched = json.loads(response["message"]["content"])

        # Skip if not software-solvable
        if not enriched.get("is_software_solvable", True):
            return None

        return {
            "description": enriched.get("description", problem_data["description"]),
            "problem_frequency": enriched.get("problem_frequency"),
            "existing_solutions": enriched.get("existing_solutions"),
            "pricing_estimate": enriched.get("pricing_estimate"),
            "tech_stack_options": enriched.get("tech_stack_options"),
            "recommended_tech_stack": enriched.get("recommended_tech_stack"),
            "tech_stack_justification": enriched.get("tech_stack_justification"),
        }

    except Exception as e:
        print(f"AI enrichment failed: {e}")
        # Fallback to basic data
        return {
            "description": problem_data["description"] or problem_data["readme"][:200],
            "problem_frequency": None,
            "existing_solutions": None,
            "pricing_estimate": None,
        }


def _clean_title(repo_name: str) -> str:
    """Convert repo name to clean title."""
    # Remove common prefixes/suffixes
    title = repo_name.replace("-", " ").replace("_", " ")
    title = title.replace("fix my itch", "").strip()

    # Capitalize words
    return " ".join(word.capitalize() for word in title.split())
