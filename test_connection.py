from sqlalchemy import text

from database.connection import engine


try:
    with engine.connect() as connection:

        result = connection.execute(
            text("SELECT version();")
        )

        version = result.fetchone()[0]

        print("✅ Connected successfully!")
        print("PostgreSQL version:")
        print(version)

except Exception as e:

    print("❌ Connection failed!")
    print(e)