from database.base import Base
from database.connection import engine

# Import models so SQLAlchemy knows about all tables
from database.models import (
    Transaction,
    MerchantCache,
    InsightsHistory,
)


def create_tables():
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


if __name__ == "__main__":
    create_tables()