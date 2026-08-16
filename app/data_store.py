"""Small dependency-free data access layer for the Weekloom MVP."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any


ENTITY_DIRS = {
    "projects": "projects",
    "actions": "actions",
    "weeks": "weeks",
    "inbox": "inbox",
    "reviews": "reviews",
}
ACTION_STATUSES = {"todo", "doing", "done", "dropped"}
PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_dir() -> Path:
    configured = os.environ.get("WEEKLOOM_DATA_DIR")
    return Path(configured).expanduser() if configured else repository_root() / ".weekloom-data"


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,80}", value):
        raise ValueError("invalid record id")
    return value


def entity_dir(data_dir: Path, entity: str) -> Path:
    if entity not in ENTITY_DIRS:
        raise ValueError(f"unknown entity: {entity}")
    directory = data_dir / ENTITY_DIRS[entity]
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_collection(data_dir: Path, entity: str) -> list[dict[str, Any]]:
    directory = entity_dir(data_dir, entity)
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def read_record(data_dir: Path, entity: str, record_id: str) -> dict[str, Any]:
    path = entity_dir(data_dir, entity) / f"{safe_id(record_id)}.json"
    if not path.exists():
        raise FileNotFoundError(record_id)
    return json.loads(path.read_text(encoding="utf-8"))


def write_record(data_dir: Path, entity: str, record: dict[str, Any]) -> None:
    record_id = safe_id(str(record["id"]))
    path = entity_dir(data_dir, entity) / f"{record_id}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def current_week(data_dir: Path) -> dict[str, Any] | None:
    weeks = read_collection(data_dir, "weeks")
    if not weeks:
        return None
    active = [week for week in weeks if week.get("status") in {"active", "planning"}]
    return sorted(active or weeks, key=lambda item: item.get("week_start", ""), reverse=True)[0]


def summary(data_dir: Path) -> dict[str, Any]:
    projects = read_collection(data_dir, "projects")
    actions = read_collection(data_dir, "actions")
    weeks = read_collection(data_dir, "weeks")
    inbox = read_collection(data_dir, "inbox")
    reviews = read_collection(data_dir, "reviews")
    week = current_week(data_dir)
    week_id = week.get("id") if week else None
    week_actions = [action for action in actions if action.get("week_id") == week_id]
    return {
        "data_dir": str(data_dir),
        "week": week,
        "projects": sorted(projects, key=lambda item: item.get("updated_at", ""), reverse=True),
        "actions": sorted(week_actions, key=lambda item: (item.get("status") == "done", PRIORITY_ORDER.get(item.get("priority", "normal"), 9), item.get("title", ""))),
        "inbox": sorted([item for item in inbox if item.get("status") == "open"], key=lambda item: item.get("captured_at", ""), reverse=True),
        "review": next((item for item in reviews if item.get("week_id") == week_id), None),
        "counts": {
            "projects": len(projects),
            "active_projects": sum(item.get("status") == "active" for item in projects),
            "week_actions": len(week_actions),
            "done_actions": sum(item.get("status") == "done" for item in week_actions),
            "open_inbox": sum(item.get("status") == "open" for item in inbox),
        },
    }


def create_inbox_item(data_dir: Path, title: str, notes: str = "") -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValueError("title is required")
    timestamp = dt.datetime.now().astimezone()
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:45] or "item"
    record_id = f"inbox_{timestamp.strftime('%Y%m%d%H%M%S%f')}_{slug}"
    record = {
        "id": record_id,
        "title": title,
        "notes": notes.strip(),
        "status": "open",
        "captured_at": timestamp.isoformat(timespec="seconds"),
        "processed_at": None,
        "converted_to_type": None,
        "converted_to_id": None,
    }
    write_record(data_dir, "inbox", record)
    return record


def update_action_status(data_dir: Path, action_id: str, status: str) -> dict[str, Any]:
    if status not in ACTION_STATUSES:
        raise ValueError(f"invalid action status: {status}")
    action = read_record(data_dir, "actions", action_id)
    action["status"] = status
    action["updated_at"] = now_iso()
    action["completed_at"] = now_iso() if status == "done" else None
    write_record(data_dir, "actions", action)
    return action


def upsert_review(data_dir: Path, week_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9]{4}-W[0-9]{2}", week_id):
        raise ValueError("invalid week id")
    existing = next((item for item in read_collection(data_dir, "reviews") if item.get("week_id") == week_id), None)
    timestamp = now_iso()
    record = existing or {
        "id": f"review_{week_id.replace('-', '_').lower()}",
        "week_id": week_id,
        "created_at": timestamp,
    }
    for field in ("wins", "unfinished", "blockers", "decisions", "next_week_focus"):
        value = payload.get(field, [])
        record[field] = value if isinstance(value, list) else [line.strip() for line in str(value).splitlines() if line.strip()]
    rating = payload.get("overall_rating")
    record["overall_rating"] = int(rating) if rating not in (None, "",) else None
    record["notes"] = str(payload.get("notes", "")).strip()
    record["updated_at"] = timestamp
    write_record(data_dir, "reviews", record)
    return record
