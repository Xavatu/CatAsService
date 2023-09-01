import os
from functools import wraps

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "catservice")
DB_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

Base = declarative_base()
engine = create_async_engine(DB_URL, echo=False)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def async_session_injector(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if "session" in kwargs:
            return await func(*args, **kwargs)
        async with async_session() as session:
            return await func(*args, **kwargs, session=session)

    return wrapper
