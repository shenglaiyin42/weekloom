#!/usr/bin/env python3
"""Move a processed Codex review request from pending to completed."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from data_store import complete_review_request, default_data_dir  # noqa: E402


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-dir", type=Path, default=default_data_dir())
parser.add_argument("--request-id", required=True)
parser.add_argument("--status", choices=["completed", "failed"], default="completed")
parser.add_argument("--note", default=None)
args = parser.parse_args()

record = complete_review_request(args.data_dir, args.request_id, args.status, args.note)
print(f"Archived {record['id']} as {record['status']}")
