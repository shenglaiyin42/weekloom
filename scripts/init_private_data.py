#!/usr/bin/env python3
"""Copy anonymous examples into an ignored local data directory for first use."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("examples/data"))
    parser.add_argument("--target", type=Path, default=Path(".weekloom-data"))
    parser.add_argument("--force", action="store_true", help="replace existing target files")
    args = parser.parse_args()
    args.target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source in args.source.rglob("*.json"):
        destination = args.target / source.relative_to(args.source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not args.force:
            continue
        shutil.copy2(source, destination)
        copied += 1
    print(f"Copied {copied} example JSON file(s) to {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
