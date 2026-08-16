from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from data_store import create_action, create_inbox_item, create_project, create_review_request, ensure_current_week, process_inbox_item, read_record, summary, update_action_status, update_week, upsert_review  # noqa: E402


class WeekloomDataStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="weekloom-test-"))
        source = Path(__file__).resolve().parents[1] / "examples" / "data"
        shutil.copytree(source, self.temp_dir, dirs_exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def test_summary_reads_current_week(self) -> None:
        result = summary(self.temp_dir)
        self.assertEqual(result["week"]["id"], "2026-W33")
        self.assertEqual(result["counts"]["week_actions"], 2)
        self.assertEqual(result["counts"]["done_actions"], 1)

    def test_action_status_update_is_persisted(self) -> None:
        update_action_status(self.temp_dir, "act_review_schema", "done")
        action = read_record(self.temp_dir, "actions", "act_review_schema")
        self.assertEqual(action["status"], "done")
        self.assertIsNotNone(action["completed_at"])

    def test_inbox_item_is_created(self) -> None:
        item = create_inbox_item(self.temp_dir, "测试收集", "备注")
        self.assertEqual(item["status"], "open")
        self.assertTrue((self.temp_dir / "inbox" / f"{item['id']}.json").exists())

    def test_review_is_updated(self) -> None:
        review = upsert_review(self.temp_dir, "2026-W33", {"wins": ["完成测试"], "overall_rating": "5"})
        self.assertEqual(review["wins"], ["完成测试"])
        self.assertEqual(review["overall_rating"], 5)
        stored = json.loads((self.temp_dir / "reviews" / "review_2026_w33.json").read_text())
        self.assertEqual(stored["wins"], ["完成测试"])

    def test_project_and_action_are_created_and_linked_to_week(self) -> None:
        project = create_project(self.temp_dir, {"name": "新项目", "category": "personal_project", "goal": "完成结果"})
        week = ensure_current_week(self.temp_dir)
        action = create_action(self.temp_dir, {"title": "完成第一步", "project_id": project["id"], "is_next_action": True, "week_id": week["id"]})
        self.assertEqual(action["project_id"], project["id"])
        self.assertIn(action["id"], read_record(self.temp_dir, "weeks", week["id"])["action_ids"])
        self.assertEqual(read_record(self.temp_dir, "projects", project["id"])["next_action_id"], action["id"])

    def test_codex_review_request_is_written_to_pending(self) -> None:
        request = create_review_request(self.temp_dir, "2026-W33")
        pending = self.temp_dir / "requests" / "pending" / f"{request['id']}.json"
        self.assertTrue(pending.exists())
        self.assertEqual(json.loads(pending.read_text())["status"], "pending")

    def test_week_settings_are_updated(self) -> None:
        week = update_week(self.temp_dir, "2026-W33", {"theme": "测试主题", "core_outcomes": ["成果一", "成果二", "成果三", "超出限制"]})
        self.assertEqual(week["theme"], "测试主题")
        self.assertEqual(week["core_outcomes"], ["成果一", "成果二", "成果三"])

    def test_inbox_item_can_be_converted_to_action(self) -> None:
        item = create_inbox_item(self.temp_dir, "整理收集事项")
        result = process_inbox_item(self.temp_dir, item["id"], "action", {"category": "personal_life"})
        self.assertEqual(result["inbox"]["status"], "processed")
        self.assertEqual(result["inbox"]["converted_to_type"], "action")
        self.assertEqual(read_record(self.temp_dir, "actions", result["created"]["id"])["title"], "整理收集事项")


if __name__ == "__main__":
    unittest.main()
