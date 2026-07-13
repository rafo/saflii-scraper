"""Resolve duplicate documents after a re-scrape.

SAFLII corrects document titles retroactively. A re-scrape then downloads
the same judgment under a new filename, leaving the old file behind. The
neutral citation in every filename (e.g. "[2024] ZAWCHC 147") is SAFLII's
stable key, so duplicates are detected per directory by grouping files
with the same citation and extension: the newest file (mtime) is kept,
older ones are deleted.

Usage:
    uv run python reconcile.py                # dry run against DEFAULT_DATA_DIR
    uv run python reconcile.py --apply        # actually delete
    uv run python reconcile.py /path/to/base  # other base directory

A JSON log of every deletion is written next to this script when --apply
is used (reconcile_log_<timestamp>.json).
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime

from saflii_processor_yearly import DEFAULT_DATA_DIR
from saflii_utils import CITATION_PATTERN

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def find_duplicates(base_dir):
    """Yield (directory, citation, kept_file, [older duplicates]) tuples."""
    for dirpath, _dirnames, filenames in os.walk(base_dir):
        groups = defaultdict(list)
        for name in filenames:
            match = CITATION_PATTERN.search(name)
            if not match:
                continue
            ext = os.path.splitext(name)[1].lower()
            groups[(match.group(0), ext)].append(name)

        for (citation, _ext), names in sorted(groups.items()):
            if len(names) < 2:
                continue
            names.sort(
                key=lambda n: os.path.getmtime(os.path.join(dirpath, n)),
                reverse=True,
            )
            yield dirpath, citation, names[0], names[1:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_dir", nargs="?", default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--apply", action="store_true", help="delete duplicates (default: dry run)"
    )
    args = parser.parse_args()

    if not os.path.isdir(args.base_dir):
        log.error(f"Base directory not found: {args.base_dir}")
        sys.exit(1)

    log_entries = []
    removed = 0
    for dirpath, citation, kept, older in find_duplicates(args.base_dir):
        log.info(f"{citation} in {os.path.relpath(dirpath, args.base_dir)}:")
        log.info(f"  keep:   {kept}")
        for name in older:
            log.info(f"  remove: {name}")
            if args.apply:
                os.remove(os.path.join(dirpath, name))
            removed += 1
        log_entries.append(
            {"dir": dirpath, "citation": citation, "kept": kept, "removed": older}
        )

    if not log_entries:
        log.info("No duplicates found.")
        return

    verb = "removed" if args.apply else "would remove (dry run, use --apply)"
    log.info(f"{removed} file(s) {verb} across {len(log_entries)} citation(s).")

    if args.apply:
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"reconcile_log_{datetime.now():%Y%m%d_%H%M%S}.json",
        )
        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump(log_entries, fh, ensure_ascii=False, indent=2)
        log.info(f"Log written to {log_path}")


if __name__ == "__main__":
    main()
