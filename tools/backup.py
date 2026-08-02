"""
Back up the Learning Engine.

Most of the database is reproducible — delete it, run tools/backfill.py, and the
messages, labels and topics all come back, because classification is
deterministic and Discord still holds every message.

Three things cannot be reproduced, and they are the reason this script exists:

  * your !learn fix corrections (label_source='human'), which are the training
    signal for any future classifier
  * data/learning/channels.json, the channel id mapping
  * data/syllabus.json, if you have edited it

    python3 tools/backup.py              write a new backup, prune old ones
    python3 tools/backup.py --list       show what exists
    python3 tools/backup.py --restore backups/learning-20260802-0300.tar.gz

Uses SQLite's online backup API rather than copying the file, so it is safe to
run while the bot is writing — a plain `cp` of a WAL database can produce a
corrupt copy.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("LEARNING_DB_PATH", REPO / "data/learning/learning.db"))
BACKUP_DIR = Path(os.getenv("LEARNING_BACKUP_DIR", REPO / "backups"))
KEEP = int(os.getenv("LEARNING_BACKUP_KEEP", "14"))

EXTRA_FILES = [
    REPO / "data/learning/channels.json",
    REPO / "data/syllabus.json",
]


def _stamp() -> str:
    ist = datetime.now(timezone.utc) + timedelta(minutes=330)
    return ist.strftime("%Y%m%d-%H%M")


def create() -> Path | None:
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH} — nothing to back up yet.")
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"learning-{_stamp()}.tar.gz"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "learning.db"

        # Online backup API: consistent snapshot even mid-write.
        src = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        dst = sqlite3.connect(str(tmp_db))
        with dst:
            src.backup(dst)
        dst.close()
        src.close()

        # Sanity check before we call it a backup.
        check = sqlite3.connect(str(tmp_db))
        ok = check.execute("PRAGMA integrity_check").fetchone()[0]
        messages = check.execute(
            "SELECT COUNT(*) FROM messages WHERE deleted_at IS NULL").fetchone()[0]
        corrections = check.execute(
            "SELECT COUNT(*) FROM classifications WHERE label_source='human'").fetchone()[0]
        check.close()

        if ok != "ok":
            print(f"Integrity check failed ({ok}) — backup aborted.")
            return None

        with tarfile.open(target, "w:gz") as tar:
            tar.add(tmp_db, arcname="learning.db")
            for extra in EXTRA_FILES:
                if extra.exists():
                    tar.add(extra, arcname=extra.name)

    size_kb = target.stat().st_size / 1024
    print(f"Backed up {messages} messages ({corrections} manual corrections) "
          f"-> {target.name}  [{size_kb:.0f} KB]")
    prune()
    return target


def prune() -> None:
    backups = sorted(BACKUP_DIR.glob("learning-*.tar.gz"))
    for old in backups[:-KEEP]:
        old.unlink()
        print(f"  pruned {old.name}")


def listing() -> None:
    backups = sorted(BACKUP_DIR.glob("learning-*.tar.gz"), reverse=True)
    if not backups:
        print(f"No backups in {BACKUP_DIR}")
        return
    print(f"{len(backups)} backup(s) in {BACKUP_DIR}:\n")
    for b in backups:
        size = b.stat().st_size / 1024
        when = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {b.name:<34} {size:>7.0f} KB   {when}")


def restore(archive: Path) -> int:
    if not archive.exists():
        print(f"No such backup: {archive}")
        return 1

    if DB_PATH.exists():
        safety = DB_PATH.with_suffix(f".db.before-restore-{_stamp()}")
        shutil.copy2(DB_PATH, safety)
        print(f"Current database saved as {safety.name}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name == "learning.db":
                extracted = tar.extractfile(member)
                DB_PATH.write_bytes(extracted.read())
                print(f"Restored {DB_PATH}")
            elif member.name == "channels.json":
                extracted = tar.extractfile(member)
                (DB_PATH.parent / "channels.json").write_bytes(extracted.read())
                print("Restored channels.json")

    # WAL sidecars belong to the replaced database, not this one.
    for sidecar in (DB_PATH.with_suffix(".db-wal"), DB_PATH.with_suffix(".db-shm")):
        if sidecar.exists():
            sidecar.unlink()

    print("\nRestart the bot to pick up the restored database.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Back up the Learning Engine database")
    p.add_argument("--list", action="store_true", help="list existing backups")
    p.add_argument("--restore", metavar="ARCHIVE", help="restore from a backup")
    args = p.parse_args()

    if args.list:
        listing()
        return 0
    if args.restore:
        return restore(Path(args.restore))
    return 0 if create() else 1


if __name__ == "__main__":
    raise SystemExit(main())
