#!/usr/bin/env python3
"""
scripts/export_traces.py — export the analysed episodes to JSONL for the artifact,
with an anonymity check (post hoc; reviewer item L).

Exports, per database, the rows of the analysed run_ids:

  armavour_audit     matrix-full-e1e2
  armavour_ablation  ablation-config-01, ablation-noconfig-01
  armavour_rerun     rerun-baseline-t07-01, rerun-fixed-t07-01

Fields: config fields (run_id, config_hash, site, pattern, intensity, language /
ui_language / instruction_language, agent, llm, seed, testbed_variant, code_sha),
outcome fields (outcome, placed, avoided, judge_flag, terminal_reason), steps,
trace and oracle_result where the database has them. For the matrix,
instruction_language and arm are derived with scripts/analysis.py (the columns
were never persisted).

Anonymity check: every field of every row is scanned BEFORE anything is
written. The run fails (exit 1, nothing written) if any field contains
  - a git author name, name token (>= 5 letters), email, or email local part
    (read from `git log` at run time, so this file names no one);
  - the local OS user name or home directory;
  - a local user path (X:\\Users\\..., /Users/..., /home/...);
  - an email address that is not an obvious placeholder (agents type addresses
    such as example@email.com into forms; those are allowed and counted);
  - any term listed in --deny-file (one per line, e.g. institution names;
    default results/anonymity_denylist.txt if present, which is gitignored and outside
    the export folder; never ship it).

Read-only: every connection runs SET default_transaction_read_only = on.

  python scripts/export_traces.py                 # all three databases
  python scripts/export_traces.py --check-only    # scan, write nothing
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import getpass
import hashlib
import json
import os
import re
import subprocess
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Iterable

from sqlalchemy import text

from scripts.analyze_ablation import read_only_engine

REPO = Path(__file__).resolve().parent.parent
DB = "postgresql+psycopg://armavour:armavour@localhost:5433/{}"
SOURCES = {
    "armavour_audit": ["matrix-full-e1e2"],
    "armavour_ablation": ["ablation-config-01", "ablation-noconfig-01"],
    "armavour_rerun": ["rerun-baseline-t07-01", "rerun-fixed-t07-01"],
}
WANTED = ("id", "run_id", "config_hash", "site", "pattern", "intensity", "language", "ui_language", "instruction_language",
          "agent", "llm", "seed", "testbed_variant", "code_sha", "outcome", "placed", "avoided", "judge_flag",
          "terminal_reason", "steps", "trace", "oracle_result")
OUT_DIR = REPO / "results" / "export"
PLACEHOLDER_DOMAINS = {"example.com", "example.org", "example.net", "email.com", "domain.com", "test.com"}
PLACEHOLDER_LOCAL = re.compile(r"^(example|test|dummy|temp|placeholder|anonymous|user|sample|fake|noreply|no-reply)[\w.+-]*$", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
USER_PATH = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"']+|/Users/[^/\s\"']+|/home/[^/\s\"']+)", re.I)


# --- identifying terms (collected at run time) ---------------------------------------


def git_identities(repo: Path = REPO) -> list[str]:
    try:
        out = subprocess.run(["git", "log", "--format=%an%n%ae%n%cn%n%ce"], cwd=repo, capture_output=True, check=True).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.CalledProcessError):
        return []
    terms: set[str] = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        terms.add(line)
        if "@" in line:
            local = line.split("@", 1)[0]
            terms.add(local.split("+", 1)[-1])  # 1234+handle@users.noreply.github.com -> handle
        else:
            terms.update(tok for tok in re.split(r"[\s._-]+", line) if len(tok) >= 5)
    return sorted(terms)


def local_identities() -> list[str]:
    terms = set()
    try:
        terms.add(getpass.getuser())
    except Exception:  # noqa: BLE001 - no user name on some CI hosts
        pass
    terms.add(str(Path.home()))
    return sorted(t for t in terms if t and len(t) >= 3)


def deny_terms(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def build_matchers(terms: Iterable[str]) -> list[tuple[str, re.Pattern[str]]]:
    out = []
    for i, t in enumerate(sorted(set(terms), key=len, reverse=True)):
        out.append((f"term#{i}", re.compile(re.escape(t), re.I)))
    return out


def is_placeholder_email(addr: str) -> bool:
    local, domain = addr.lower().rsplit("@", 1)
    return domain in PLACEHOLDER_DOMAINS or bool(PLACEHOLDER_LOCAL.match(local))


def scan_value(value: str, matchers: list[tuple[str, re.Pattern[str]]]) -> tuple[list[str], int]:
    """Return (violations, placeholder_email_count) for one serialized field."""
    hits = [f"identifying term ({name})" for name, rx in matchers if rx.search(value)]
    if USER_PATH.search(value):
        hits.append("local user path")
    placeholders = 0
    for addr in EMAIL.findall(value):
        if is_placeholder_email(addr):
            placeholders += 1
        else:
            hits.append("non-placeholder email address")
    return hits, placeholders


# --- data ------------------------------------------------------------------------------


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def load(db: str, run_ids: list[str], url: str | None = None) -> list[dict[str, Any]]:
    engine = read_only_engine(url or DB.format(db))
    with engine.connect() as conn:
        cols = {r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'episodes'"))}
        select = [c for c in WANTED if c in cols]
        rows = [dict(r) for r in conn.execute(text(f"SELECT {', '.join(select)} FROM episodes WHERE run_id = ANY(:r) ORDER BY id"), {"r": run_ids}).mappings()]
    engine.dispose()
    for row in rows:
        for key in ("trace", "oracle_result"):
            if isinstance(row.get(key), str):
                row[key] = json.loads(row[key])
    if db == "armavour_audit":
        from scripts.analysis import _derive_instruction_language
        from scripts.run_matrix import get_batch_name_for_config
        for row in rows:
            row["ui_language"] = row["language"]
            row["instruction_language"] = _derive_instruction_language(row)
            row["arm"] = get_batch_name_for_config(SimpleNamespace(llm=row["llm"], agent=row["agent"], seed=row["seed"],
                                                                   instruction_language=row["instruction_language"], ui_language=row["ui_language"]))
    return [{k: _jsonable(v) for k, v in row.items()} for row in rows]


def check_rows(rows: list[dict[str, Any]], matchers: list[tuple[str, re.Pattern[str]]], db: str) -> tuple[list[str], int]:
    problems, placeholders = [], 0
    for row in rows:
        for key, value in row.items():
            if value is None:
                continue
            s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            hits, ph = scan_value(s, matchers)
            placeholders += ph
            problems += [f"{db} id={row.get('id')} field={key}: {h}" for h in hits]
    return problems, placeholders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export analysed episodes to JSONL with an anonymity check (read-only).")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--deny-file", type=Path, default=REPO / "results" / "anonymity_denylist.txt")
    parser.add_argument("--db", action="append", choices=sorted(SOURCES), help="limit to these databases (repeatable)")
    parser.add_argument("--check-only", action="store_true", help="scan only; write nothing")
    args = parser.parse_args(argv)

    denied = deny_terms(args.deny_file)
    terms = git_identities() + local_identities() + denied
    matchers = build_matchers(terms)
    data, problems, placeholders = {}, [], 0
    for db in args.db or list(SOURCES):
        rows = load(db, SOURCES[db], os.getenv(f"{db.upper()}_URL"))
        data[db] = rows
        p, ph = check_rows(rows, matchers, db)
        problems += p
        placeholders += ph
        print(f"{db}: {len(rows)} rows scanned, {len(p)} violations, {ph} placeholder emails")
    if problems:
        print(f"ANONYMITY CHECK FAILED: {len(problems)} violation(s); nothing written. First 20:")
        for p in problems[:20]:
            print("  -", p)
        return 1
    print(f"Anonymity check passed ({len(matchers)} identifying terms, {placeholders} placeholder emails allowed).")
    if args.check_only:
        return 0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"generated_by": "scripts/export_traces.py", "anonymity_check": "passed",
                                "identifying_terms_checked": len(matchers), "deny_file_terms": len(denied),
                                "placeholder_emails_allowed": placeholders, "files": {}}
    for db, rows in data.items():
        path = args.out_dir / f"{db}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        manifest["files"][path.name] = {"rows": len(rows), "run_ids": SOURCES[db], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(f"wrote {path} ({len(rows)} rows)")
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
