from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])

hashes = [
    "a7ad606a2b1cc52c605d9699b0bedaeb3fc2f5edf128921084e37493cc0ebd46",
    "ef8aa1d741f5adc8a547177f4b8ea2d325aa098b8e92cf42596a484c3b1439ee",
    "6ac829278ae1197de4a4b8e1e7c38f0b7174823e7cb333b21ae92dcd33c16b75",
    "127f290afd8883f8a0d28c26bcdd3766635816c7f8272507a353baf4a9ab5b02",
    "feacf12dc77d8ecf2c474e911c57acc11b5aa4efea8de2ff07235a7bc6242aee",
]

with engine.connect() as conn:
    for h in hashes:
        row = conn.execute(
            text("SELECT trace FROM episodes WHERE config_hash = :h ORDER BY config_hash"),
            {"h": h},
        ).fetchone()
        print(f"\n--- {h[:12]}... ---")
        print(row[0] if row else "NO ROW FOUND")
        