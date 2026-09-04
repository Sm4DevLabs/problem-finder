"""
Lobsters connector — public story-listing JSON feed.

STATUS: implemented but disabled-by-default. See "Access policy" below
before enabling this in production.

Lobste.rs exposes unauthenticated, read-only JSON feeds for its story
listings. Verified live on 2026-09-04 by fetching real data:

    https://lobste.rs/newest.json           # newest submissions, most recent first
    https://lobste.rs/newest.json?page=N    # pagination (~24-25 items/page)
    https://lobste.rs/hottest.json          # front-page ranking
    https://lobste.rs/<tag>.json            # tag-filtered feed, e.g. /security.json

Confirmed responses (fetched today, 2026-09-04):
  - GET https://lobste.rs/newest.json returned a live story with
    created_at "2026-09-03T23:44:04.467-05:00", short_id "r58i7h",
    title "Lua-async", tags ["lua", "vim"].
  - GET https://lobste.rs/hottest.json?page=2 returned 24 more live
    stories (e.g. short_id "6tsncg", ".name Termination").

Each story object in the array looks like::

    {
      "short_id": "r58i7h",
      "created_at": "2026-09-03T23:44:04.467-05:00",
      "title": "Lua-async",
      "url": "https://neovim.io/doc/user/lua-async/",
      "score": 2,
      "flags": 0,
      "comment_count": 0,
      "description": "",              # HTML body, empty for link-only posts
      "description_plain": "",        # plain-text body
      "submitter_user": "adaszko",
      "user_is_author": false,
      "tags": ["lua", "vim"],
      "short_id_url": "https://lobste.rs/s/r58i7h",
      "comments_url": "https://lobste.rs/s/r58i7h/lua_async"
    }

No API key, login, or paid plan is required to make the HTTP request
itself — it's a plain, unauthenticated GET.

ACCESS POLICY — WHY THIS ADAPTER IS DISABLED BY DEFAULT
--------------------------------------------------------
https://lobste.rs/robots.txt explicitly disallows every crawler except a
short, named allowlist of search engines:

    User-agent: Applebot
    User-agent: BingBot
    User-agent: DuckDuckBot
    User-agent: GoogleBot
    User-agent: ia_archiver
    User-agent: Kagibot
    User-agent: Slurp
    Allow: /
    Disallow: /search
    Disallow: /page/
    Disallow: /comments/page/

    Content-Signal: ai-input=no, ai-train=no, search=yes

    User-agent: *
    Crawl-delay: 1
    Disallow: /

Any bot that is not on that named list — including a backend service
like this one, identifying itself with its own User-Agent — falls under
the `User-Agent: *` rule, which disallows the *entire site* (`Disallow: /`),
covering the .json feeds too. The file's own header comment says how to
get added to the allowlist: "PR https://github.com/lobsters/lobsters to
be added to the list" — i.e. it requires the Lobsters maintainers'
discretionary review and approval, not a self-serve signup a
ProblemFinder user could complete on their own. The `Content-Signal:
ai-input=no` line additionally states the operator's wish that site
content not be used as input to an AI system, which is exactly this
pipeline's use case.

Because of this, `fetch()` below is fully implemented and was manually
verified to work against live data, but it refuses to run unless the
environment variable `LOBSTERS_IGNORE_ROBOTS=true` is explicitly set, so
nobody enables it by accident against the site's stated access policy.
Do not set that flag unless you have obtained explicit, out-of-band
permission from the Lobsters maintainers to fetch this feed
programmatically; the sanctioned route is to pursue allowlisting via the
PR process referenced in their robots.txt.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.connectors.clients.api_client import get_json
from app.connectors.common import build_raw_data, stable_id, truncate_title

load_dotenv()

LOBSTERS_BASE_URL = "https://lobste.rs"
DEFAULT_LIMIT = 20
_PAGE_SIZE = 25  # observed items per page on lobste.rs's *.json feeds
_MAX_PAGES = 10  # safety cap so a bad limit can't loop indefinitely


def _map_story(item: dict) -> dict | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None

    short_id = item.get("short_id")
    story_page_url = item.get("short_id_url") or (
        f"{LOBSTERS_BASE_URL}/s/{short_id}" if short_id else LOBSTERS_BASE_URL
    )
    # Prefer the externally-linked article; fall back to the Lobsters
    # discussion page for text-only/self posts.
    external_url = item.get("url") or story_page_url

    description = (item.get("description_plain") or "").strip() or title

    tags = item.get("tags") or []
    category = tags[0] if tags else None

    return {
        "external_id": stable_id("lobsters", short_id or story_page_url),
        "title": truncate_title(title),
        "description": description,
        "url": external_url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        "problem_author": None,
        "raw_data": build_raw_data(
            "lobsters",
            external_url,
            strategy="api",
            category=category,
            industry=None,
            score=item.get("score"),
            extra={
                "short_id": short_id,
                "story_page_url": story_page_url,
                "comments_url": item.get("comments_url"),
                "comment_count": item.get("comment_count"),
                "tags": tags,
                "submitter_user": item.get("submitter_user"),
                "created_at": item.get("created_at"),
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch recent Lobsters stories from the public /newest.json feed.

    Args:
        limit: Max problems to return. None => a default batch of ~20.

    Raises:
        RuntimeError: always, unless LOBSTERS_IGNORE_ROBOTS=true is set in
            the environment (or a loaded .env file). See the module
            docstring: lobste.rs's robots.txt disallows non-whitelisted
            crawlers (including backend services like this one) from the
            entire site, and its Content-Signal header opts out of
            AI-input use. This guard exists so the adapter can never be
            enabled silently against the site's stated access policy.
    """
    if os.getenv("LOBSTERS_IGNORE_ROBOTS", "").strip().lower() != "true":
        raise RuntimeError(
            "Lobsters adapter is disabled: https://lobste.rs/robots.txt disallows "
            "all crawlers other than a named list of search engines (Googlebot, "
            "Bingbot, DuckDuckBot, Applebot, Kagibot, Slurp, ia_archiver), and its "
            "Content-Signal header sets ai-input=no. Getting this source's bot "
            "allowlisted requires opening a PR against "
            "https://github.com/lobsters/lobsters for the maintainers to review at "
            "their discretion -- it is not a self-serve API key a user can obtain. "
            "If you have obtained explicit, out-of-band permission from the "
            "Lobsters maintainers to fetch this feed programmatically, set "
            "LOBSTERS_IGNORE_ROBOTS=true (env var or .env) to enable this adapter."
        )

    effective_limit = limit if limit is not None else DEFAULT_LIMIT

    problems: list[dict] = []
    seen_ids: set[str] = set()
    page = 1
    while len(problems) < effective_limit and page <= _MAX_PAGES:
        data = await get_json(f"{LOBSTERS_BASE_URL}/newest.json", params={"page": page})
        if not isinstance(data, list) or not data:
            break

        for item in data:
            mapped = _map_story(item)
            if mapped and mapped["external_id"] not in seen_ids:
                seen_ids.add(mapped["external_id"])
                problems.append(mapped)
            if len(problems) >= effective_limit:
                break

        if len(data) < _PAGE_SIZE:
            break  # last page
        page += 1

    print(f"Lobsters: Extracted {len(problems)} stories from /newest.json ({page} page(s))")
    return problems
