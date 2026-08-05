import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.postgres_models import Base
from app.core.config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in your .env file")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()