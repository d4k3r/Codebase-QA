"""Create MVP database tables from SQLAlchemy metadata."""

from app.database import engine
from app.models import Base


def main() -> None:
    """Create tables that do not already exist."""

    Base.metadata.create_all(bind=engine)
    print("Database tables initialized.")


if __name__ == "__main__":
    main()
