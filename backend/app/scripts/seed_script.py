import asyncio

from sqlalchemy import select

from app.database.database_session import AsyncSessionLocal
from app.models.source_model import Source


async def seed_sources():
    """Seed the database with initial source data."""
    # Start with 8 ACTIVE sources focused on real problems that can become apps
    # Not open-source contribution tasks or datasets
    initial_sources = [
        # 1. PEOPLE_SUBMITTED_PROBLEMS - Highest quality, explicitly curated problems
        {
            "name": "Razorpay Fix My Itch",
            "source_type": "PEOPLE_SUBMITTED_PROBLEMS",
            "homepage_url": "https://razorpay.com/m/fix-my-itch/",
            "collection_method": None,  # Will be assessed
            "is_active": True,
        },
        {
            "name": "ProblemHunt",
            "source_type": "PEOPLE_SUBMITTED_PROBLEMS",
            "homepage_url": "https://problemhunt.pro/",
            "collection_method": None,
            "is_active": True,
        },
        # 2. COMMUNITY_PAIN_DISCUSSIONS - Real frustrations from various communities
        {
            "name": "Hacker News",
            "source_type": "COMMUNITY_PAIN_DISCUSSIONS",
            "homepage_url": "https://news.ycombinator.com/",
            "collection_method": None,
            "is_active": True,
        },
        {
            "name": "Reddit",
            "source_type": "COMMUNITY_PAIN_DISCUSSIONS",
            "homepage_url": "https://www.reddit.com/",
            "collection_method": None,
            "is_active": True,
        },
        {
            "name": "Stack Exchange",
            "source_type": "COMMUNITY_PAIN_DISCUSSIONS",
            "homepage_url": "https://stackexchange.com/",
            "collection_method": None,
            "is_active": True,
        },
        # 3. CUSTOMER_COMPLAINTS - Real consumer pain points
        {
            "name": "CFPB Consumer Complaint Database",
            "source_type": "CUSTOMER_COMPLAINTS",
            "homepage_url": "https://www.consumerfinance.gov/data-research/consumer-complaints/",
            "collection_method": None,
            "is_active": True,
        },
        # 4. CIVIC_PUBLIC_PROBLEMS - Public sector challenges
        {
            "name": "Civic Tech Field Guide",
            "source_type": "CIVIC_PUBLIC_PROBLEMS",
            "homepage_url": "https://directory.civictech.guide/",
            "collection_method": None,
            "is_active": True,
        },
        # 5. CHALLENGE_STATEMENTS - Well-defined real-world problems
        {
            "name": "Kaggle Competitions",
            "source_type": "CHALLENGE_STATEMENTS",
            "homepage_url": "https://www.kaggle.com/competitions",
            "collection_method": None,
            "is_active": True,
        },
        {
            "name": "Indie Hackers",
            "source_type": "PEOPLE_SUBMITTED_PROBLEMS",
            "homepage_url": "https://www.indiehackers.com/",
            "collection_method": None,
            "is_active": True,
        },
        {
            "name": "NYC 311 Service Requests",
            "source_type": "CIVIC_PUBLIC_PROBLEMS",
            "homepage_url": "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9",
            "collection_method": None,
            "is_active": True,
        },
        {
            "name": "Open Government Partnership",
            "source_type": "CIVIC_PUBLIC_PROBLEMS",
            "homepage_url": "https://www.opengovpartnership.org/the-open-gov-challenge/",
            "collection_method": None,
            "is_active": True,
        },
        {
            "name": "NASA Space Apps Challenge",
            "source_type": "CHALLENGE_STATEMENTS",
            "homepage_url": "https://www.spaceappschallenge.org/",
            "collection_method": None,
            "is_active": True,
        },
        {
            "name": "DrivenData Competitions",
            "source_type": "CHALLENGE_STATEMENTS",
            "homepage_url": "https://www.drivendata.org/competitions/",
            "collection_method": None,
            "is_active": True,
        },
        # INACTIVE: lobste.rs/robots.txt disallows non-allowlisted crawlers.
        # See app/connectors/adapters/lobsters.py. Flip only with explicit,
        # out-of-band permission from the Lobsters maintainers.
        {
            "name": "Lobsters",
            "source_type": "COMMUNITY_PAIN_DISCUSSIONS",
            "homepage_url": "https://lobste.rs/",
            "collection_method": None,
            "is_active": False,
        },
    ]

    inserted_count = 0
    skipped_count = 0
    total_sources = len(initial_sources)

    async with AsyncSessionLocal() as session:
        try:
            for source_data in initial_sources:
                # Check if source already exists
                result = await session.execute(
                    select(Source).where(Source.name == source_data["name"])
                )
                existing_source = result.scalar_one_or_none()

                if existing_source:
                    print(f"⏭️  Skipped: {source_data['name']} (already exists)")
                    skipped_count += 1
                    continue

                # Create and add new source
                new_source = Source(**source_data)
                session.add(new_source)
                inserted_count += 1
                print(f"✅ Inserted: {source_data['name']}")

            # Commit all changes
            await session.commit()
            print(f"\n{'='*60}")
            print(f"✅ Seeding complete!")
            print(f"📊 Inserted: {inserted_count}")
            print(f"⏭️  Skipped: {skipped_count}")
            print(f"📝 Total: {total_sources}")
            print(f"{'='*60}")

        except Exception as e:
            await session.rollback()
            print(f"❌ Error occurred: {e}")
            raise


if __name__ == "__main__":
    print("🌱 Starting database seeding...\n")
    asyncio.run(seed_sources())
