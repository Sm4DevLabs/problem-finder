"""Maps a Source.name to its adapter's fetch function.

Add a new source by adding one entry here and one module in adapters/.

Notes on specific adapters:
- "Lobsters" is registered but its fetch() always raises unless the
  LOBSTERS_IGNORE_ROBOTS env var is explicitly set — lobste.rs's robots.txt
  disallows non-allowlisted crawlers. Keep the matching Source row
  is_active=False unless that permission has been obtained.
- "Reddit" needs REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET (free, self-serve).
- "Kaggle Competitions" needs KAGGLE_USERNAME/KAGGLE_KEY (free, self-serve).
See each adapter module's docstring for setup details.
"""

from app.connectors.adapters import (
    cfpb,
    civic_tech_field_guide,
    drivendata,
    hackernews,
    indie_hackers,
    kaggle,
    lobsters,
    nasa_space_apps,
    nyc_311,
    ogp,
    problemhunt,
    razorpay,
    reddit,
    stackexchange,
)
from app.connectors.base import FetchFn

ADAPTERS: dict[str, FetchFn] = {
    "ProblemHunt": problemhunt.fetch,
    "Razorpay Fix My Itch": razorpay.fetch,
    "Hacker News": hackernews.fetch,
    "Stack Exchange": stackexchange.fetch,
    "Reddit": reddit.fetch,
    "CFPB Consumer Complaint Database": cfpb.fetch,
    "Civic Tech Field Guide": civic_tech_field_guide.fetch,
    "Kaggle Competitions": kaggle.fetch,
    "Indie Hackers": indie_hackers.fetch,
    "Lobsters": lobsters.fetch,
    "NYC 311 Service Requests": nyc_311.fetch,
    "Open Government Partnership": ogp.fetch,
    "NASA Space Apps Challenge": nasa_space_apps.fetch,
    "DrivenData Competitions": drivendata.fetch,
}
