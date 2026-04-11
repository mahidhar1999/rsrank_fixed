from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # reconnect on stale connections
    pool_recycle=3600,        # recycle connections every hour
)

def get_db():
    """FastAPI dependency — yields a SQLAlchemy connection."""
    with engine.connect() as conn:
        yield conn

def execute_sql_file(path: str):
    """Utility to run a .sql file against the database."""
    with open(path, "r") as f:
        sql = f.read()
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
