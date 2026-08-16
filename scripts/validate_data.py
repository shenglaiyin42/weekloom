#!/usr/bin/env python3
"""Validate Weekloom JSON data with the repository's dependency-free schema subset."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_BY_DIR = {
    "projects": "project.schema.json",
    "actions": "action.schema.json",
    "weeks": "week.schema.json",
    "inbox": "inbox-item.schema.json",
    "reviews": "review.schema.json",
}
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


class ValidationError(Exception):
    """A readable data validation failure."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}") from exc


def resolve_ref(ref: str) -> dict[str, Any]:
    file_name, _, fragment = ref.partition("#")
    schema = load_json(SCHEMA_DIR / file_name)
    value: Any = schema
    for part in fragment.lstrip("/").split("/") if fragment else []:
        value = value[part]
    return value


def validate(value: Any, schema: dict[str, Any], path: str) -> None:
    if "$ref" in schema:
        validate(value, resolve_ref(schema["$ref"]), path)
        return

    expected = schema.get("type")
    expected_types = expected if isinstance(expected, list) else [expected]
    if expected and not any(type_matches(value, type_name) for type_name in expected_types):
        raise ValidationError(f"{path}: expected {expected}, got {type(value).__name__}")

    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: {value!r} is not one of {schema['enum']}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValidationError(f"{path}: string is shorter than minLength")
        if len(value) > schema.get("maxLength", float("inf")):
            raise ValidationError(f"{path}: string is longer than maxLength")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ValidationError(f"{path}: {value!r} does not match {schema['pattern']!r}")
        if schema.get("format") == "date":
            try:
                dt.date.fromisoformat(value)
            except ValueError as exc:
                raise ValidationError(f"{path}: invalid ISO date") from exc
        if schema.get("format") == "date-time":
            try:
                dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValidationError(f"{path}: invalid ISO date-time") from exc

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", float("-inf")):
            raise ValidationError(f"{path}: value is below minimum")
        if value > schema.get("maximum", float("inf")):
            raise ValidationError(f"{path}: value is above maximum")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValidationError(f"{path}: array has too few items")
        if len(value) > schema.get("maxItems", float("inf")):
            raise ValidationError(f"{path}: array has too many items")
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], f"{path}[{index}]")

    if isinstance(value, dict):
        for required in schema.get("required", []):
            if required not in value:
                raise ValidationError(f"{path}: missing required property {required!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                raise ValidationError(f"{path}: unexpected properties {unexpected}")
        for key, child in value.items():
            if key in properties:
                validate(child, properties[key], f"{path}.{key}")


def type_matches(value: Any, type_name: str | None) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(type_name, True)


def validate_references(records: dict[str, dict[str, Any]]) -> None:
    projects = records.get("projects", {})
    actions = records.get("actions", {})
    weeks = records.get("weeks", {})
    reviews = records.get("reviews", {})

    for action in actions.values():
        project_id = action.get("project_id")
        week_id = action.get("week_id")
        if project_id and project_id not in projects:
            raise ValidationError(f"action {action['id']}: unknown project_id {project_id!r}")
        if week_id and week_id not in weeks:
            raise ValidationError(f"action {action['id']}: unknown week_id {week_id!r}")

    for project in projects.values():
        next_action_id = project.get("next_action_id")
        if next_action_id and next_action_id not in actions:
            raise ValidationError(f"project {project['id']}: unknown next_action_id {next_action_id!r}")

    for week in weeks.values():
        for action_id in week.get("action_ids", []):
            if action_id not in actions:
                raise ValidationError(f"week {week['id']}: unknown action_id {action_id!r}")

    for review in reviews.values():
        if review.get("week_id") not in weeks:
            raise ValidationError(f"review {review['id']}: unknown week_id {review['week_id']!r}")


def validate_directory(data_dir: Path) -> int:
    records: dict[str, dict[str, Any]] = {key: {} for key in SCHEMA_BY_DIR}
    count = 0
    for directory, schema_name in SCHEMA_BY_DIR.items():
        entity_dir = data_dir / directory
        if not entity_dir.exists():
            continue
        for path in sorted(entity_dir.glob("*.json")):
            value = load_json(path)
            validate(value, load_json(SCHEMA_DIR / schema_name), str(path))
            entity_id = value.get("id") if isinstance(value, dict) else None
            if entity_id in records[directory]:
                raise ValidationError(f"{path}: duplicate id {entity_id!r}")
            records[directory][entity_id] = value
            count += 1
    validate_references(records)
    print(f"Validated {count} JSON file(s) in {data_dir}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("examples/data"), help="Data directory to validate")
    args = parser.parse_args()
    try:
        validate_directory(args.data_dir)
    except (OSError, KeyError, ValidationError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
