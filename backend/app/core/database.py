from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Convert postgresql:// to postgresql+asyncpg://
database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def run_migrations(conn):
    """Run manual migrations to add new columns"""
    migrations = [
        # Add new camera columns if they don't exist
        ("cameras", "save_snapshots", "BOOLEAN DEFAULT true"),
        ("cameras", "save_video_clips", "BOOLEAN DEFAULT false"),
        ("cameras", "video_clip_duration", "INTEGER DEFAULT 10"),
        ("cameras", "notification_cooldown", "INTEGER DEFAULT 60"),
    ]
    
    for table, column, definition in migrations:
        try:
            # Check if column exists
            result = await conn.execute(text(f"""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name = '{column}'
            """))
            row = result.fetchone()
            
            if not row:
                # Add column
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                logger.info(f"Added column {column} to {table}")
        except Exception as e:
            logger.warning(f"Migration for {table}.{column} skipped: {e}")


async def init_db():
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Run migrations for new columns
        await run_migrations(conn)
