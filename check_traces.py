from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT config_hash, trace FROM episodes WHERE pattern = 'basket_sneaking' ORDER BY config_hash")
    ).fetchall()
    for r in rows:
        print(r[0])
        actions = [step.get("action") for step in r[1]] if isinstance(r[1], list) else r[1]
        print(actions)
        print("---")