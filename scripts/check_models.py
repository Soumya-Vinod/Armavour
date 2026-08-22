from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    print("=== by llm / agent / intensity ===")
    rows = conn.execute(text("""
        SELECT llm, agent, intensity, count(*) AS n,
               min(created_at)::date AS first_run,
               sum(case when outcome='DC' then 1 else 0 end) AS dc
        FROM episodes
        WHERE run_id = :rid
        GROUP BY 1,2,3
        ORDER BY 1,2,3
    """), {"rid": "matrix-full-e1e2"}).fetchall()
    for r in rows:
        print(f"  {r[0]:<32} {r[1]:<12} {r[2]:<11} n={r[3]:<5} first={r[4]} DC={r[5]}")

    print("\n=== distinct llm values across ALL run_ids ===")
    rows = conn.execute(text("""
        SELECT run_id, llm, count(*)
        FROM episodes
        GROUP BY 1,2
        ORDER BY 1,2
    """)).fetchall()
    for r in rows:
        print(f"  {r[0]:<34} {r[1]:<32} {r[2]}")