import asyncio

from sqlalchemy import select

from app.database.database_session import AsyncSessionLocal
from app.models.source_model import Source


async def seed_sources():
    """Seed the database with initial source data."""
    initial_sources = [
        {
            "name": "Razorpay Fix My Itch",
            "source_type": "PEOPLE_SUBMITTED_PROBLEMS",
            "homepage_url": "https://razorpay.com/m/fix-my-itch/",
            "collection_method": "API",
        },
        {
            "name": "ProblemHunt",
            "source_type": "PEOPLE_SUBMITTED_PROBLEMS",
            "homepage_url": "https://problemhunt.pro/",
            "collection_method": "WEB_SCRAPING",
        },
        {
            "name": "Reddit",
            "source_type": "CUSTOMER_COMPLAINTS",
            "homepage_url": "https://www.reddit.com/",
            "collection_method": "API",
        },
        {
            "name": "G2",
            "source_type": "CUSTOMER_COMPLAINTS",
            "homepage_url": "https://www.g2.com/",
            "collection_method": "MANUAL",
        },
        {
            "name": "GitHub Issues",
            "source_type": "OPEN_SOURCE_PROBLEMS",
            "homepage_url": "https://github.com/issues",
            "collection_method": "API",
        },
        {
            "name": "Good First Issue",
            "source_type": "OPEN_SOURCE_PROBLEMS",
            "homepage_url": "https://goodfirstissue.dev/",
            "collection_method": "API",
        },
        {
            "name": "Devpost",
            "source_type": "HACKATHON_CHALLENGES",
            "homepage_url": "https://devpost.com/hackathons",
            "collection_method": "WEB_SCRAPING",
        },
        {
            "name": "Kaggle Competitions",
            "source_type": "HACKATHON_CHALLENGES",
            "homepage_url": "https://www.kaggle.com/competitions",
            "collection_method": "API",
        },
        {
            "name": "Challenge.gov",
            "source_type": "CIVIC_PUBLIC_PROBLEMS",
            "homepage_url": "https://www.challenge.gov/",
            "collection_method": "WEB_SCRAPING",
        },
        {
            "name": "Civic Tech Field Guide",
            "source_type": "CIVIC_PUBLIC_PROBLEMS",
            "homepage_url": "https://directory.civictech.guide/",
            "collection_method": "API",
        },
        {
            "name": "Data.gov",
            "source_type": "DATASETS_AND_PUBLIC_APIS",
            "homepage_url": "https://data.gov/",
            "collection_method": "API",
        },
        {
            "name": "Kaggle Datasets",
            "source_type": "DATASETS_AND_PUBLIC_APIS",
            "homepage_url": "https://www.kaggle.com/datasets",
            "collection_method": "API",
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
