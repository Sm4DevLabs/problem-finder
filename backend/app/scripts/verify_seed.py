import asyncio

from sqlalchemy import select

from app.database.database_session import AsyncSessionLocal
from app.models.source_model import Source


async def verify_seeded_data():
    """Verify seeded data in the database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Source))
        sources = result.scalars().all()

        print(f"\n{'='*70}")
        print(f"📊 Total Sources in Database: {len(sources)}")
        print(f"{'='*70}\n")

        for i, source in enumerate(sources, 1):
            print(f"{i}. {source.name}")
            print(f"   Type: {source.source_type}")
            print(f"   URL: {source.homepage_url}")
            print(f"   Method: {source.collection_method}")
            print(f"   Status: {source.assessment_status}")
            print(f"   ID: {source.id}")
            print(f"   Created: {source.created_at}")
            print()


if __name__ == "__main__":
    asyncio.run(verify_seeded_data())
