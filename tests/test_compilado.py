"""Leitura das edições do Compilado e regra de primeira execução."""

import json
import unittest
from datetime import date, datetime, timezone
from unittest import mock

from feeds.integrations.compilado import Compilado
from feeds.integrations.compilado.models import Edition
from feeds.integrations.compilado.source import parse_home, split_title


def home_html(articles):
    data = {"props": {"pageProps": {"channelProps": {"homeData": {"articles": articles}}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


class ParseTest(unittest.TestCase):
    def test_split_title(self):
        self.assertEqual(
            split_title("COMPILADO #263 - Líderes tech divergem sobre frear IA; CEO da Automattic de volta; "),
            ("COMPILADO #263", ["Líderes tech divergem sobre frear IA", "CEO da Automattic de volta"]),
        )

    def test_parse_home_sorts_and_skips_unpublished(self):
        editions = parse_home(home_html([
            {"uid": "2", "title": "COMPILADO #2 - B", "slug": "ep3", "publishedDate": "2026-09-26T19:08:09.351Z"},
            {"uid": "x", "title": "Rascunho", "slug": "draft", "publishedDate": None},
            {"uid": "1", "title": "COMPILADO #1 - A", "slug": "ep2", "publishedDate": "2026-09-18T18:28:35.769Z"},
        ]), "https://site/")
        self.assertEqual([e.uid for e in editions], ["1", "2"])
        self.assertEqual(editions[1].link, "https://site/ep3")
        self.assertEqual(editions[1].headlines, ["B"])

    def test_missing_next_data_raises(self):
        with self.assertRaises(RuntimeError):
            parse_home("<html></html>", "https://site/")


class BootstrapTest(unittest.TestCase):
    def edition(self, uid, iso):
        return Edition(uid=uid, name=uid, title=uid, link="", published=datetime.fromisoformat(iso))

    def test_first_run_skips_editions_before_today_in_brasilia(self):
        old = self.edition("old", "2026-09-26T19:00:00+00:00")
        # 29/09 01:00 UTC ainda é 28/09 em Brasília → conta como "antes de hoje"
        late_night = self.edition("late", "2026-09-29T01:00:00+00:00")
        today = self.edition("today", "2026-09-29T15:00:00+00:00")

        integ = Compilado(http=None, state=mock.Mock(), log=lambda _: None)
        with mock.patch.object(Compilado, "today", return_value=date(2026, 9, 29)):
            skipped = integ.bootstrap([old, late_night, today])
        self.assertEqual([e.uid for e in skipped], ["old", "late"])


if __name__ == "__main__":
    unittest.main()
