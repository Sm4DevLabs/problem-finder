"""
Reddit connector — OAuth2 "script" app + oauth.reddit.com JSON listings.

Reddit's unauthenticated `https://www.reddit.com/r/<sub>/top.json` trick still
exists, but it is aggressively rate-limited/blocked for non-browser traffic
(especially from datacenter/cloud IPs, which is exactly where a backend
service runs), so this adapter uses Reddit's officially supported OAuth2 API
instead:

  1. Log into any Reddit account and open https://www.reddit.com/prefs/apps
  2. Click "create app" / "create another app", choose type **script**
  3. Any redirect URI works for script apps (Reddit's own docs suggest
     http://localhost:8080 as a placeholder — it is never actually hit)
  4. Reddit immediately issues a client id (the string under the app name)
     and a client secret — no approval queue, no payment, no waiting period

Docs used (verified live via WebFetch on 2026-09-04):
  - https://github.com/reddit-archive/reddit/wiki/OAuth2
    (token endpoint, Basic-auth-with-client-id/secret, client_credentials
    grant for app-only/"userless" access, oauth.reddit.com host)
  - https://praw.readthedocs.io/en/stable/getting_started/authentication.html
    (confirms script-app registration is free/self-serve; no fees, no
    approval process beyond the self-service form)

Flow implemented here (app-only OAuth, no end-user Reddit login needed):
  1. POST https://www.reddit.com/api/v1/access_token
     - HTTP Basic auth: username=client_id, password=client_secret
     - form body: grant_type=client_credentials
     - -> {"access_token": "...", "token_type": "bearer", "expires_in": 3600, ...}
  2. GET https://oauth.reddit.com/r/<subreddit>/top?limit=...&t=...
     - Header: Authorization: bearer <access_token>
     - Header: User-Agent: <descriptive UA, ideally including your username>

NOTE FOR REVIEWERS: this environment's WebFetch tool refused to resolve any
`reddit.com` / `redditinc.com` hostname directly ("unable to fetch from
<host>" — an environment-level restriction, not a Reddit-side outage), and
its WebSearch tool errored on every query attempted while writing this file.
The OAuth2 mechanics above were therefore confirmed via the reddit-archive
GitHub wiki and the actively-maintained PRAW docs (both fetchable), not via
a live end-to-end call against oauth.reddit.com itself. The flow has been
Reddit's stable, documented, free-tier OAuth2 mechanism for many years and
is what every third-party Reddit client uses, but please smoke-test this
adapter with real REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET credentials before
relying on it in production, in case Reddit has since tightened app-only
("userless") access to public listings.

Required environment variables (add to backend/.env, see .env.example):
  REDDIT_CLIENT_ID       - client id from your script app (free, self-serve)
  REDDIT_CLIENT_SECRET   - client secret from your script app
  REDDIT_USER_AGENT      - optional; a descriptive UA string. Reddit's own
                           guidance is "<platform>:<app id>:<version> (by
                           /u/<your-username>)" — including a real username
                           reduces the odds of being rate-limited harder.
  REDDIT_SUBREDDITS      - optional; comma-separated subreddit names to pull
                           from. Defaults to a curated list of subreddits
                           where people post "I wish this existed" / product
                           problem requests (SomebodyMakeThis, Lightbulb,
                           AppIdeas).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from app.connectors.clients.api_client import get_json
from app.connectors.common import build_raw_data, stable_id, truncate_title

load_dotenv()

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_BASE_URL = "https://oauth.reddit.com"
DEFAULT_USER_AGENT = "ProblemFinder/1.0 (backend connector; +https://github.com/subh2312/problem-finder)"
DEFAULT_SUBREDDITS = ["SomebodyMakeThis", "Lightbulb", "AppIdeas"]
DEFAULT_LIMIT = 20
DEFAULT_TIME_FILTER = "month"


def _subreddits() -> list[str]:
    raw = os.getenv("REDDIT_SUBREDDITS")
    if not raw:
        return DEFAULT_SUBREDDITS
    names = [name.strip().lstrip("r/").strip() for name in raw.split(",")]
    return [name for name in names if name]


async def _get_access_token(client_id: str, client_secret: str, user_agent: str) -> str:
    """Exchange the script app's client id/secret for an app-only bearer token.

    Uses plain httpx (not the shared get_json helper) because this is a POST
    with HTTP Basic auth and a form body — get_json only handles GET+JSON.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            response = await client.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=httpx.BasicAuth(client_id, client_secret),
                headers={"User-Agent": user_agent},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPStatusError, httpx.TransportError) as e:
        raise RuntimeError(
            f"Reddit OAuth token request failed ({e}). Verify REDDIT_CLIENT_ID / "
            "REDDIT_CLIENT_SECRET are correct and the app at "
            "https://www.reddit.com/prefs/apps is still type 'script'."
        ) from e

    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token:
        raise RuntimeError(f"Reddit OAuth token response missing access_token: {payload}")
    return token


def _map_post(post: dict[str, Any], subreddit: str) -> dict[str, Any] | None:
    title = (post.get("title") or "").strip()
    if not title:
        return None
    # Stickied posts are almost always mod announcements/rules, not problems.
    # over_18 (NSFW) posts are filtered out as unsuitable for the feed.
    if post.get("stickied") or post.get("over_18"):
        return None

    permalink = post.get("permalink") or ""
    url = f"https://www.reddit.com{permalink}" if permalink else (post.get("url") or f"https://www.reddit.com/r/{subreddit}/")
    natural_key = post.get("name") or permalink or url

    selftext = (post.get("selftext") or "").strip()
    description = selftext if selftext and selftext not in ("[removed]", "[deleted]") else title

    author = post.get("author")
    problem_author = f"u/{author}" if author and author not in ("[deleted]", "[removed]") else None

    return {
        "external_id": stable_id("reddit", natural_key),
        "title": truncate_title(title),
        "description": description,
        "url": url,
        "problem_frequency": None,
        "existing_solutions": None,
        "pricing_estimate": None,
        "problem_author": problem_author,
        "raw_data": build_raw_data(
            "reddit",
            url,
            strategy="api",
            category=subreddit,
            industry=None,
            score=post.get("score"),
            extra={
                "post_id": post.get("id"),
                "subreddit": subreddit,
                "num_comments": post.get("num_comments"),
                "created_utc": post.get("created_utc"),
                "is_self": post.get("is_self"),
                "link_flair_text": post.get("link_flair_text"),
                "external_link": None if post.get("is_self") else post.get("url"),
            },
        ),
    }


async def fetch(limit: int | None = None) -> list[dict]:
    """
    Fetch candidate "problem" posts from a curated set of Reddit subreddits.

    Args:
        limit: Max problems to return. None fetches a reasonable default
            batch (~20).
    """
    max_items = limit if limit is not None else DEFAULT_LIMIT

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Reddit adapter requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET "
            "environment variables. Create a free 'script' app at "
            "https://www.reddit.com/prefs/apps (type: script, any redirect URI "
            "e.g. http://localhost:8080), then set REDDIT_CLIENT_ID to the id "
            "shown under the app name and REDDIT_CLIENT_SECRET to the secret "
            "shown next to it in your .env file."
        )

    user_agent = os.getenv("REDDIT_USER_AGENT", DEFAULT_USER_AGENT)
    token = await _get_access_token(client_id, client_secret, user_agent)
    headers = {"Authorization": f"bearer {token}", "User-Agent": user_agent}

    subreddits = _subreddits()
    per_subreddit_limit = min(100, max(25, max_items))

    problems: list[dict] = []
    seen_ids: set[str] = set()
    errors: list[str] = []

    for subreddit in subreddits:
        if len(problems) >= max_items:
            break
        try:
            data = await get_json(
                f"{OAUTH_BASE_URL}/r/{subreddit}/top",
                params={"limit": per_subreddit_limit, "t": DEFAULT_TIME_FILTER, "raw_json": 1},
                headers=headers,
            )
        except Exception as e:
            errors.append(f"r/{subreddit}: {e}")
            continue

        children = ((data or {}).get("data") or {}).get("children") or []
        for child in children:
            post = child.get("data") or {}
            mapped = _map_post(post, subreddit)
            if not mapped:
                continue
            if mapped["external_id"] in seen_ids:
                continue
            seen_ids.add(mapped["external_id"])
            problems.append(mapped)
            if len(problems) >= max_items:
                break

    if not problems and errors:
        raise RuntimeError(f"Reddit fetch failed for all subreddits: {'; '.join(errors)}")

    print(
        f"Reddit: Extracted {len(problems)} problems from {len(subreddits)} subreddits "
        f"({len(errors)} subreddit fetch errors)"
    )
    return problems
