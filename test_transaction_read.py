from database.connection import get_session
from database.models import Transaction

session = get_session()

if session is None:
    print("Database is not configured.")
else:
    try:
        transaction = session.query(Transaction).first()
        print("Transaction read successful.")
        print(transaction)
    except Exception as exc:
        print("Transaction read failed:", repr(exc))
        session.rollback()
    finally:
        session.close()