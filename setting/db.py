from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from setting.base import DATABASE_URI, SESSION_POOL_SIZE

engine = create_engine(
    DATABASE_URI,
    pool_size=SESSION_POOL_SIZE,
    max_overflow=20,
    pool_timeout=60,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 60,
        "read_timeout": 300,
        "write_timeout": 300,
    },
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
