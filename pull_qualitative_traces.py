from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    print("=" * 60)
    print("interface_interference — all episodes (sanity check on 0% result)")
    print("=" * 60)
    rows = conn.execute(
        text("SELECT config_hash, intensity, outcome, trace FROM episodes "
             "WHERE pattern = 'interface_interference' ORDER BY intensity, config_hash")
    ).fetchall()
    for r in rows:
        print(f"\n[{r[1]}] outcome={r[2]} hash={r[0][:12]}...")
        actions = [step.get("action") for step in r[3]] if isinstance(r[3], list) else r[3]
        print("  actions:", actions)
        if isinstance(r[3], list):
            for step in r[3]:
                if step.get("reasoning"):
                    print("  reasoning:", step["reasoning"][:200])

    print("\n" + "=" * 60)
    print("saas_billing — all episodes (highest DPSR, qualitative pass)")
    print("=" * 60)
    rows = conn.execute(
        text("SELECT config_hash, intensity, outcome, trace FROM episodes "
             "WHERE pattern = 'saas_billing' ORDER BY intensity, config_hash")
    ).fetchall()
    for r in rows:
        print(f"\n[{r[1]}] outcome={r[2]} hash={r[0][:12]}...")
        if isinstance(r[3], list):
            for step in r[3]:
                if step.get("reasoning"):
                    print(f"  step {step.get('step')}: {step.get('action')} — {step['reasoning'][:200]}")