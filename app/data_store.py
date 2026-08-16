"""Small dependency-free data access layer for the Weekloom MVP."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
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
CATEGORIES = {"work", "personal_project", "personal_life", "interest_learning"}
PROJECT_STATUSES = {"active", "waiting", "paused", "completed", "archived"}
WEEK_ROLES = {"focus", "planned", "candidate", "recurring"}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_dir() -> Path:
    configured = os.environ.get("WEEKLOOM_DATA_DIR")
    return Path(configured).expanduser() if configured else repository_root() / ".weekloom-data"


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def safe_id(value: str) -> str:
    if not (re.fullmatch(r"[a-z][a-z0-9_-]{2,80}", value) or re.fullmatch(r"[0-9]{4}-W[0-9]{2}", value)):
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


def pending_request_dir(data_dir: Path) -> Path:
    directory = data_dir / "requests" / "pending"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def pending_requests(data_dir: Path) -> list[dict[str, Any]]:
    directory = pending_request_dir(data_dir)
    records = []
    for path in sorted(directory.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def git_sync_status(data_dir: Path) -> dict[str, Any]:
    """Return read-only local Git status without exposing remote URLs or file contents."""
    if not (data_dir / ".git").exists():
        return {"configured": False, "message": "私人数据目录尚未初始化 Git"}
    try:
        result = subprocess.run(
            ["git", "-C", str(data_dir), "status", "--porcelain=1", "--branch"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        lines = [line for line in result.stdout.splitlines() if line]
        branch = lines[0].removeprefix("## ") if lines and lines[0].startswith("## ") else "unknown"
        changes = lines[1:] if lines and lines[0].startswith("## ") else lines
        remote = subprocess.run(
            ["git", "-C", str(data_dir), "remote"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return {
            "configured": True,
            "branch": branch,
            "has_remote": bool(remote.stdout.strip()),
            "dirty": bool(changes),
            "change_count": len(changes),
            "message": "有本地更改尚未提交" if changes else "本地 Git 工作区干净",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"configured": False, "message": f"无法读取私人数据 Git 状态：{exc}"}


def current_week(data_dir: Path) -> dict[str, Any] | None:
    weeks = read_collection(data_dir, "weeks")
    if not weeks:
        return None
    today = dt.date.today()
    in_range = [
        week for week in weeks
        if week.get("status") in {"active", "planning"}
        and str(week.get("week_start", "")) <= today.isoformat() <= str(week.get("week_end", ""))
    ]
    if in_range:
        return sorted(in_range, key=lambda item: item.get("week_start", ""), reverse=True)[0]
    active = [week for week in weeks if week.get("status") in {"active", "planning"}]
    return sorted(active or weeks, key=lambda item: item.get("week_start", ""), reverse=True)[0]


def ensure_current_week(data_dir: Path) -> dict[str, Any]:
    """Return the current local week, creating a planning week when needed."""
    existing = current_week(data_dir)
    today = dt.date.today()
    if existing and str(existing.get("week_start", "")) <= today.isoformat() <= str(existing.get("week_end", "")):
        return existing
    monday = today - dt.timedelta(days=today.weekday())
    sunday = monday + dt.timedelta(days=6)
    year, week_number, _ = today.isocalendar()
    week_id = f"{year}-W{week_number:02d}"
    record = {
        "id": week_id,
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "status": "planning",
        "theme": "",
        "core_outcomes": [],
        "action_ids": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    write_record(data_dir, "weeks", record)
    return record


def start_next_week(data_dir: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create the next planning week without copying actions or changing the current week."""
    payload = payload or {}
    weeks = read_collection(data_dir, "weeks")
    if not weeks:
        return ensure_current_week(data_dir)
    latest = max(weeks, key=lambda item: str(item.get("week_end", item.get("week_start", ""))))
    base_week = current_week(data_dir) or latest
    latest_end = dt.date.fromisoformat(str(base_week["week_end"]))
    monday = latest_end + dt.timedelta(days=1)
    while monday.weekday() != 0:
        monday += dt.timedelta(days=1)
    year, week_number, _ = monday.isocalendar()
    week_id = f"{year}-W{week_number:02d}"
    existing = next((week for week in weeks if week.get("id") == week_id), None)
    if existing:
        return existing
    review = next((item for item in read_collection(data_dir, "reviews") if item.get("week_id") == base_week.get("id")), None)
    outcomes = payload.get("core_outcomes")
    if outcomes is None:
        outcomes = (review or {}).get("next_week_focus", [])
    if not isinstance(outcomes, list):
        outcomes = [line.strip() for line in str(outcomes).splitlines() if line.strip()]
    outcomes = [str(item).strip() for item in outcomes if str(item).strip()][:3]
    timestamp = now_iso()
    record = {
        "id": week_id,
        "week_start": monday.isoformat(),
        "week_end": (monday + dt.timedelta(days=6)).isoformat(),
        "status": "planning",
        "theme": str(payload.get("theme", "")).strip(),
        "core_outcomes": outcomes,
        "action_ids": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    write_record(data_dir, "weeks", record)
    return record


def summary(data_dir: Path) -> dict[str, Any]:
    projects = read_collection(data_dir, "projects")
    actions = read_collection(data_dir, "actions")
    weeks = read_collection(data_dir, "weeks")
    inbox = read_collection(data_dir, "inbox")
    reviews = read_collection(data_dir, "reviews")
    requests = pending_requests(data_dir)
    sync = git_sync_status(data_dir)
    week = current_week(data_dir)
    week_id = week.get("id") if week else None
    week_actions = [action for action in actions if action.get("week_id") == week_id]
    today = dt.date.today()
    stalled_cutoff = today - dt.timedelta(days=14)
    attention_projects = []
    for project in projects:
        updated_date = str(project.get("updated_at", ""))[:10]
        is_stalled = project.get("status") == "active" and (
            not project.get("next_action_id") or (updated_date and updated_date < stalled_cutoff.isoformat())
        )
        if project.get("status") in {"waiting", "paused"} or project.get("progress", 0) < 25 or is_stalled:
            attention_projects.append({
                "id": project.get("id"),
                "name": project.get("name"),
                "status": project.get("status"),
                "progress": project.get("progress", 0),
                "blocked_reason": project.get("blocked_reason"),
                "stalled": is_stalled,
            })
    overdue_actions = [
        {"id": action.get("id"), "title": action.get("title"), "due_date": action.get("due_date"), "status": action.get("status")}
        for action in week_actions
        if action.get("due_date") and str(action["due_date"]) < today.isoformat() and action.get("status") not in {"done", "dropped"}
    ]
    return {
        "data_dir": str(data_dir),
        "week": week,
        "projects": sorted(projects, key=lambda item: item.get("updated_at", ""), reverse=True),
        "actions": sorted(week_actions, key=lambda item: (item.get("status") == "done", PRIORITY_ORDER.get(item.get("priority", "normal"), 9), item.get("title", ""))),
        "inbox": sorted([item for item in inbox if item.get("status") == "open"], key=lambda item: item.get("captured_at", ""), reverse=True),
        "review": next((item for item in reviews if item.get("week_id") == week_id), None),
        "pending_requests": requests,
        "sync": sync,
        "attention": {"projects": attention_projects, "overdue_actions": overdue_actions},
        "counts": {
            "projects": len(projects),
            "active_projects": sum(item.get("status") == "active" for item in projects),
            "week_actions": len(week_actions),
            "done_actions": sum(item.get("status") == "done" for item in week_actions),
            "open_inbox": sum(item.get("status") == "open" for item in inbox),
            "pending_requests": len(requests),
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


def process_inbox_item(data_dir: Path, inbox_id: str, target_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    item = read_record(data_dir, "inbox", inbox_id)
    if item.get("status") != "open":
        raise ValueError("inbox item is already processed")
    payload = payload or {}
    if target_type == "action":
        created = create_action(data_dir, {
            "title": item["title"],
            "notes": item.get("notes", ""),
            "category": payload.get("category", "personal_life"),
            "priority": payload.get("priority", "normal"),
            "weekly_role": payload.get("weekly_role", "planned"),
        })
    elif target_type == "project":
        created = create_project(data_dir, {
            "name": item["title"],
            "description": item.get("notes", ""),
            "goal": payload.get("goal", item["title"]),
            "category": payload.get("category", "personal_project"),
        })
    elif target_type == "dismiss":
        created = None
    else:
        raise ValueError(f"invalid inbox target: {target_type}")
    item["status"] = "dismissed" if target_type == "dismiss" else "processed"
    item["processed_at"] = now_iso()
    item["converted_to_type"] = None if target_type == "dismiss" else target_type
    item["converted_to_id"] = None if created is None else created["id"]
    write_record(data_dir, "inbox", item)
    return {"inbox": item, "created": created}


def create_project(data_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("project name is required")
    category = str(payload.get("category", "personal_project"))
    if category not in CATEGORIES:
        raise ValueError(f"invalid project category: {category}")
    status = str(payload.get("status", "active"))
    if status not in PROJECT_STATUSES:
        raise ValueError(f"invalid project status: {status}")
    timestamp = now_iso()
    record = {
        "id": f"proj_{dt.datetime.now().astimezone().strftime('%Y%m%d%H%M%S%f')}",
        "name": name,
        "description": str(payload.get("description", "")).strip(),
        "goal": str(payload.get("goal", "")).strip() or name,
        "category": category,
        "status": status,
        "progress": 0,
        "target_date": payload.get("target_date") or None,
        "next_action_id": None,
        "tags": payload.get("tags", []) if isinstance(payload.get("tags", []), list) else [],
        "blocked_reason": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "completed_at": None,
    }
    write_record(data_dir, "projects", record)
    return record


def update_project(data_dir: Path, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    project = read_record(data_dir, "projects", project_id)
    status = str(payload.get("status", project.get("status", "active")))
    if status not in PROJECT_STATUSES:
        raise ValueError(f"invalid project status: {status}")
    try:
        progress = int(payload.get("progress", project.get("progress", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError("project progress must be an integer") from exc
    if not 0 <= progress <= 100:
        raise ValueError("project progress must be between 0 and 100")
    if status == "completed":
        progress = 100
    project["status"] = status
    project["progress"] = progress
    if "blocked_reason" in payload:
        project["blocked_reason"] = str(payload.get("blocked_reason") or "").strip() or None
    if "target_date" in payload:
        project["target_date"] = payload.get("target_date") or None
    project["updated_at"] = now_iso()
    project["completed_at"] = project["updated_at"] if status == "completed" else None
    write_record(data_dir, "projects", project)
    return project


def create_action(data_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValueError("action title is required")
    project_id = payload.get("project_id") or None
    project = read_record(data_dir, "projects", project_id) if project_id else None
    category = str(payload.get("category") or (project or {}).get("category") or "personal_project")
    if category not in CATEGORIES:
        raise ValueError(f"invalid action category: {category}")
    priority = str(payload.get("priority", "normal"))
    if priority not in PRIORITY_ORDER:
        raise ValueError(f"invalid action priority: {priority}")
    weekly_role = str(payload.get("weekly_role", "planned"))
    if weekly_role not in WEEK_ROLES:
        raise ValueError(f"invalid weekly role: {weekly_role}")
    status = str(payload.get("status", "todo"))
    if status not in ACTION_STATUSES:
        raise ValueError(f"invalid action status: {status}")
    week = read_record(data_dir, "weeks", str(payload["week_id"])) if payload.get("week_id") else ensure_current_week(data_dir)
    timestamp = now_iso()
    record = {
        "id": f"act_{dt.datetime.now().astimezone().strftime('%Y%m%d%H%M%S%f')}",
        "title": title,
        "project_id": project_id,
        "week_id": week["id"],
        "category": category,
        "priority": priority,
        "weekly_role": weekly_role,
        "status": status,
        "is_next_action": bool(payload.get("is_next_action", False)),
        "due_date": payload.get("due_date") or None,
        "estimate_minutes": int(payload["estimate_minutes"]) if payload.get("estimate_minutes") not in (None, "") else None,
        "tags": payload.get("tags", []) if isinstance(payload.get("tags", []), list) else [],
        "notes": str(payload.get("notes", "")).strip(),
        "blocked_reason": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "completed_at": timestamp if status == "done" else None,
    }
    write_record(data_dir, "actions", record)
    if record["id"] not in week.get("action_ids", []):
        week.setdefault("action_ids", []).append(record["id"])
        week["updated_at"] = timestamp
        write_record(data_dir, "weeks", week)
    if project and (record["is_next_action"] or not project.get("next_action_id")):
        project["next_action_id"] = record["id"]
        project["updated_at"] = timestamp
        write_record(data_dir, "projects", project)
    return record


def update_week(data_dir: Path, week_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    week = read_record(data_dir, "weeks", week_id)
    outcomes = payload.get("core_outcomes", [])
    if not isinstance(outcomes, list):
        outcomes = [line.strip() for line in str(outcomes).splitlines() if line.strip()]
    outcomes = [str(item).strip() for item in outcomes if str(item).strip()][:3]
    status = str(payload.get("status", week.get("status", "planning")))
    if status not in {"planning", "active", "reviewed", "archived"}:
        raise ValueError(f"invalid week status: {status}")
    week["theme"] = str(payload.get("theme", week.get("theme", ""))).strip()
    week["core_outcomes"] = outcomes
    week["status"] = status
    week["updated_at"] = now_iso()
    write_record(data_dir, "weeks", week)
    return week


def create_review_request(data_dir: Path, week_id: str | None = None, note: str = "") -> dict[str, Any]:
    week = read_record(data_dir, "weeks", week_id) if week_id else ensure_current_week(data_dir)
    timestamp = dt.datetime.now().astimezone()
    record = {
        "id": f"request_{timestamp.strftime('%Y%m%d%H%M%S%f')}",
        "type": "weekly_review",
        "week_id": week["id"],
        "status": "pending",
        "note": note.strip(),
        "requested_actions": [
            "总结本周完成与未完成事项",
            "识别停滞、阻塞和反复延期的项目",
            "提出下周三个重点建议",
        ],
        "created_at": timestamp.isoformat(timespec="seconds"),
    }
    destination = pending_request_dir(data_dir) / f"{record['id']}.json"
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
