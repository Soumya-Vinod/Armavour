from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    print("Total episode rows:")
    print(conn.execute(text("SELECT COUNT(*) FROM episodes")).scalar())

    print("\nDistinct pattern values (with counts):")
    rows = conn.execute(text("SELECT pattern, COUNT(*) FROM episodes GROUP BY pattern ORDER BY pattern")).fetchall()
    for r in rows:
        print(f"  {r[0]!r}: {r[1]}")

    print("\nDistinct outcome values (with counts):")
    rows = conn.execute(text("SELECT outcome, COUNT(*) FROM episodes GROUP BY outcome")).fetchall()
    for r in rows:
        print(f"  {r[0]!r}: {r[1]}")