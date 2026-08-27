"""Return the database to the seeded state so a demo or acceptance run is repeatable.

Destructive by design: it lives in scripts/, never in app/, so the running service
cannot truncate its own tables.
"""

import sys

from sqlalchemy import text

from app.config import settings
from app.infrastructure.db import Base, SessionLocal
from app.infrastructure.seed import seed_if_empty


def reset_demo_data() -> int:
    if settings.database_url == settings.test_database_url:
        raise RuntimeError("Refusing to run: the application database is the test database.")

    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with SessionLocal() as session:
        session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        session.commit()
        seed_if_empty(session)
        session.commit()
        return session.execute(text("SELECT count(*) FROM orders")).scalar_one()


if __name__ == "__main__":
    print(f"Reseeded. Orders: {reset_demo_data()}", file=sys.stderr)
