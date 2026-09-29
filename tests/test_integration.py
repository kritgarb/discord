"""Fluxo da classe base Integration: deduplicação, primeira execução, --test e --dry-run."""

import tempfile
import unittest
from pathlib import Path

from feeds.core import Integration, SeenStore


class FakeWebhook:
    def __init__(self):
        self.sent = []

    def send_embed(self, embed):
        self.sent.append(embed["title"])


class FakeIntegration(Integration[str]):
    slug = title = username = "fake"
    webhook_env = "FAKE_WEBHOOK"
    SEND_INTERVAL = 0

    def __init__(self, items, state, skip_on_first_run=()):
        super().__init__(http=None, state=state, log=lambda _: None)
        self.items = items
        self.skip_on_first_run = skip_on_first_run
        self.hook = FakeWebhook()

    def fetch(self, *, full, limit):
        return list(self.items)

    def keys(self, item):
        return {item}

    def label(self, item):
        return item

    def to_embed(self, item):
        return {"title": item}

    def summary(self, item):
        return [item]

    def bootstrap(self, items):
        return [i for i in items if i in self.skip_on_first_run]

    def webhook(self):
        return self.hook


class IntegrationFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, items, **kwargs):
        return FakeIntegration(items, SeenStore(self.path), **kwargs)

    def test_first_run_posts_everything_and_saves_state(self):
        integ = self.make(["a", "b"])
        integ.run()
        self.assertEqual(integ.hook.sent, ["a", "b"])
        self.assertTrue(self.path.exists())

    def test_does_not_repost(self):
        self.make(["a", "b"]).run()
        integ = self.make(["a", "b", "c"])
        integ.run()
        self.assertEqual(integ.hook.sent, ["c"])

    def test_bootstrap_marks_items_as_seen_on_first_run_only(self):
        integ = self.make(["old", "today"], skip_on_first_run={"old"})
        integ.run()
        self.assertEqual(integ.hook.sent, ["today"])

        integ = self.make(["old", "today", "new"], skip_on_first_run={"old", "today", "new"})
        integ.run()  # não é mais a primeira execução: bootstrap não se aplica
        self.assertEqual(integ.hook.sent, ["new"])

    def test_test_mode_resends_latest_without_touching_state(self):
        self.make(["a", "b"]).run()
        before = self.path.read_text()
        integ = self.make(["a", "b"])
        integ.run(test=1)
        self.assertEqual(integ.hook.sent, ["b"])
        self.assertEqual(self.path.read_text(), before)

    def test_dry_run_sends_and_saves_nothing(self):
        integ = self.make(["a"])
        integ.run(dry_run=True)
        self.assertEqual(integ.hook.sent, [])
        self.assertFalse(self.path.exists())

    def test_any_matching_key_counts_as_seen(self):
        store = SeenStore(self.path)
        store.add({"https://site/post", "?p=1"})
        self.assertTrue(store.contains_any({"?p=1", "outro"}))
        self.assertFalse(store.contains_any({"?p=2"}))


if __name__ == "__main__":
    unittest.main()
