from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from data_store import calendar_view, complete_review_request, create_action, create_inbox_item, create_project, create_review_request, ensure_current_week, git_sync_status, process_inbox_item, read_record, start_next_week, summary, update_action, update_action_status, update_project, update_week, upsert_review  # noqa: E402


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
        self.assertTrue(any(project["id"] == "proj_weekloom" for project in result["attention"]["projects"]))

    def test_git_sync_status_is_safe_for_local_data_directory(self) -> None:
        status = git_sync_status(self.temp_dir)
        self.assertFalse(status["configured"])

    def test_action_status_update_is_persisted(self) -> None:
        update_action_status(self.temp_dir, "act_review_schema", "done")
        action = read_record(self.temp_dir, "actions", "act_review_schema")
        self.assertEqual(action["status"], "done")
        self.assertIsNotNone(action["completed_at"])

    def test_action_due_date_can_be_created_edited_and_cleared(self) -> None:
        action = create_action(self.temp_dir, {"title": "安排日期", "due_date": "2026-08-20"})
        self.assertEqual(action["due_date"], "2026-08-20")
        updated = update_action(self.temp_dir, action["id"], {"due_date": "2026-08-22"})
        self.assertEqual(updated["due_date"], "2026-08-22")
        self.assertIsNone(update_action(self.temp_dir, action["id"], {"due_date": None})["due_date"])
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            create_action(self.temp_dir, {"title": "错误日期", "due_date": "08/20/2026"})

    def test_project_status_and_progress_update_is_persisted(self) -> None:
        updated = update_project(
            self.temp_dir,
            "proj_weekloom",
            {"status": "waiting", "progress": 55, "blocked_reason": "等待反馈"},
        )
        self.assertEqual(updated["status"], "waiting")
        self.assertEqual(updated["progress"], 55)
        self.assertEqual(updated["blocked_reason"], "等待反馈")
        persisted = read_record(self.temp_dir, "projects", "proj_weekloom")
        self.assertEqual(persisted["progress"], 55)

    def test_project_target_date_can_be_created_and_edited(self) -> None:
        project = create_project(self.temp_dir, {"name": "日期项目", "target_date": "2026-08-28"})
        self.assertEqual(project["target_date"], "2026-08-28")
        updated = update_project(self.temp_dir, project["id"], {"target_date": "2026-09-01"})
        self.assertEqual(updated["target_date"], "2026-09-01")
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            update_project(self.temp_dir, project["id"], {"target_date": "next Friday"})

    def test_calendar_combines_action_deadlines_and_project_targets(self) -> None:
        action = create_action(self.temp_dir, {"title": "日历行动", "due_date": "2026-08-20"})
        project = create_project(self.temp_dir, {"name": "日历项目", "target_date": "2026-08-20"})
        calendar = calendar_view(self.temp_dir, "2026-08")
        self.assertEqual(calendar["month"], "2026-08")
        self.assertEqual(calendar["days_in_month"], 31)
        self.assertEqual(calendar["first_weekday"], 5)
        event_ids = {event["id"] for event in calendar["events"]}
        self.assertIn(action["id"], event_ids)
        self.assertIn(project["id"], event_ids)
        self.assertGreaterEqual(calendar["counts"]["events"], 2)
        with self.assertRaisesRegex(ValueError, "YYYY-MM"):
            calendar_view(self.temp_dir, "2026-13")

    def test_inbox_item_is_created(self) -> None:
        item = create_inbox_item(self.temp_dir, "测试收集", "备注")
        self.assertEqual(item["status"], "open")
        self.assertTrue((self.temp_dir / "inbox" / f"{item['id']}.json").exists())

    def test_review_is_updated(self) -> None:
        review = upsert_review(self.temp_dir, "2026-W33", {"wins": ["完成测试"], "overall_rating": "5", "notes": "本周最不顺手的是复盘入口不够明显"})
        self.assertEqual(review["wins"], ["完成测试"])
        self.assertEqual(review["overall_rating"], 5)
        self.assertIn("最不顺手", review["notes"])
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

    def test_codex_review_request_can_be_completed(self) -> None:
        request = create_review_request(self.temp_dir, "2026-W33")
        completed = complete_review_request(self.temp_dir, request["id"], note="已完成复盘并提出下周重点")
        self.assertEqual(completed["status"], "completed")
        self.assertFalse((self.temp_dir / "requests" / "pending" / f"{request['id']}.json").exists())
        self.assertTrue((self.temp_dir / "requests" / "completed" / f"{request['id']}.json").exists())

    def test_week_settings_are_updated(self) -> None:
        week = update_week(self.temp_dir, "2026-W33", {"theme": "测试主题", "core_outcomes": ["成果一", "成果二", "成果三", "超出限制"]})
        self.assertEqual(week["theme"], "测试主题")
        self.assertEqual(week["core_outcomes"], ["成果一", "成果二", "成果三"])

    def test_next_week_uses_review_focus_and_is_idempotent(self) -> None:
        next_week = start_next_week(self.temp_dir, {"theme": "下周主题"})
        self.assertEqual(next_week["id"], "2026-W34")
        self.assertEqual(next_week["theme"], "下周主题")
        self.assertEqual(next_week["core_outcomes"], ["完成最小本地 App 的第一条纵向流程"])
        self.assertEqual(next_week["action_ids"], [])
        self.assertEqual(start_next_week(self.temp_dir)["id"], "2026-W34")

    def test_inbox_item_can_be_converted_to_action(self) -> None:
        item = create_inbox_item(self.temp_dir, "整理收集事项")
        result = process_inbox_item(self.temp_dir, item["id"], "action", {"category": "personal_life"})
        self.assertEqual(result["inbox"]["status"], "processed")
        self.assertEqual(result["inbox"]["converted_to_type"], "action")
        self.assertEqual(read_record(self.temp_dir, "actions", result["created"]["id"])["title"], "整理收集事项")


if __name__ == "__main__":
    unittest.main()
