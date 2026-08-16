from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from data_store import create_inbox_item, read_record, summary, update_action_status, upsert_review  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
