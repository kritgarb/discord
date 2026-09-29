"""Regras do relógio de ponto, com relógio controlado e SQLite em memória."""

import unittest
from datetime import datetime, timedelta, timezone

from feeds.core.clock import BRT
from ponto.repository import SQLiteRepository
from ponto.service import TimeClock, TimeClockError
from ponto.timeutil import format_duration, parse_clock_time, parse_duration, period

G, ANA, BIA, ADMIN = 1, 10, 20, 99


class FakeNow:
    def __init__(self, start):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, **kwargs):
        self.t += timedelta(**kwargs)


class TimeClockTest(unittest.TestCase):
    def setUp(self):
        # quarta-feira, 30/09/2026 09:00 em Brasília
        self.now = FakeNow(datetime(2026, 9, 30, 9, 0, tzinfo=BRT).astimezone(timezone.utc))
        self.repo = SQLiteRepository(":memory:")
        self.clock = TimeClock(self.repo, now=self.now)

    def tearDown(self):
        self.repo.close()

    def work(self, user, hours, note=None):
        self.clock.clock_in(G, user, note)
        self.now.advance(hours=hours)
        return self.clock.clock_out(G, user)

    def month_total(self, user):
        totals = self.clock.totals(G, period("mes", self.now()), user)
        return totals[0].total_seconds if totals else 0

    def test_clock_in_and_out(self):
        s = self.work(ANA, 2.5)
        self.assertEqual(s.worked_seconds(s.ended_at), 2.5 * 3600)
        self.assertEqual(self.month_total(ANA), 2.5 * 3600)

    def test_cannot_clock_in_twice(self):
        self.clock.clock_in(G, ANA)
        with self.assertRaises(TimeClockError):
            self.clock.clock_in(G, ANA)

    def test_clock_out_without_open_session(self):
        with self.assertRaises(TimeClockError):
            self.clock.clock_out(G, ANA)

    def test_pauses_are_not_counted(self):
        self.clock.clock_in(G, ANA)
        self.now.advance(hours=1)
        self.clock.pause(G, ANA)
        self.now.advance(minutes=30)
        self.clock.resume(G, ANA)
        self.now.advance(hours=1)
        self.clock.pause(G, ANA)
        self.now.advance(minutes=15)
        s = self.clock.clock_out(G, ANA)  # sair em pausa: a pausa em andamento também não conta
        self.assertEqual(s.worked_seconds(s.ended_at), 2 * 3600)

    def test_pause_rules(self):
        self.clock.clock_in(G, ANA)
        with self.assertRaises(TimeClockError):
            self.clock.resume(G, ANA)
        self.clock.pause(G, ANA)
        with self.assertRaises(TimeClockError):
            self.clock.pause(G, ANA)

    def test_users_and_servers_are_independent(self):
        self.clock.clock_in(G, ANA)
        self.clock.clock_in(G, BIA)            # outra pessoa pode abrir
        self.clock.clock_in(2, ANA)            # a mesma pessoa em outro servidor também
        self.now.advance(hours=1)
        self.clock.clock_out(G, ANA)
        self.assertIsNotNone(self.clock.current(G, BIA))
        self.assertEqual([s.user_id for s in self.clock.open_sessions(G)], [BIA])

    def test_admin_closes_forgotten_session_in_the_past(self):
        self.clock.clock_in(G, ANA)
        self.now.advance(hours=10)             # esqueceu aberto até 19:00
        at = parse_clock_time("12:00", self.now())
        s = self.clock.clock_out(G, ANA, at)
        self.assertEqual(s.worked_seconds(s.ended_at), 3 * 3600)

    def test_close_time_must_be_between_start_and_now(self):
        self.clock.clock_in(G, ANA)
        self.now.advance(hours=1)
        with self.assertRaises(TimeClockError):
            self.clock.clock_out(G, ANA, self.now() - timedelta(hours=2))   # antes da entrada
        with self.assertRaises(TimeClockError):
            self.clock.clock_out(G, ANA, self.now() + timedelta(minutes=1))  # no futuro

    def test_adjustments_add_to_totals(self):
        self.work(ANA, 2)
        self.clock.adjust(G, ANA, parse_duration("1h30"), "esqueceu de bater o ponto", ADMIN)
        self.clock.adjust(G, ANA, parse_duration("-0h30"), "almoço contado", ADMIN)
        self.assertEqual(self.month_total(ANA), 3 * 3600)
        with self.assertRaises(TimeClockError):
            self.clock.adjust(G, ANA, 0, "nada", ADMIN)

    def test_open_sessions_do_not_count_until_closed(self):
        self.clock.clock_in(G, ANA)
        self.now.advance(hours=3)
        self.assertEqual(self.month_total(ANA), 0)

    def test_report_is_sorted_by_total(self):
        self.work(ANA, 1)
        self.work(BIA, 4)
        totals = self.clock.totals(G, period("mes", self.now()))
        self.assertEqual([t.user_id for t in totals], [BIA, ANA])

    def test_sessions_count_in_the_period_they_started(self):
        # entrou em 30/09 às 23:00 e saiu em 01/10 às 01:00 → conta em setembro
        self.now.t = datetime(2026, 9, 30, 23, 0, tzinfo=BRT).astimezone(timezone.utc)
        self.work(ANA, 2)
        september = period("mes-passado", self.now())
        self.assertEqual(self.clock.totals(G, september, ANA)[0].total_seconds, 2 * 3600)
        self.assertEqual(self.month_total(ANA), 0)

    def test_reminder_once_for_long_open_sessions(self):
        self.clock.clock_in(G, ANA)
        self.now.advance(hours=7)
        self.assertEqual(self.clock.sessions_to_remind(8 * 3600), [])
        self.now.advance(hours=2)
        due = self.clock.sessions_to_remind(8 * 3600)
        self.assertEqual([s.user_id for s in due], [ANA])
        self.clock.mark_reminded(due[0])
        self.assertEqual(self.clock.sessions_to_remind(8 * 3600), [])


class TimeUtilTest(unittest.TestCase):
    def test_parse_duration(self):
        self.assertEqual(parse_duration("1h30"), 5400)
        self.assertEqual(parse_duration("2h"), 7200)
        self.assertEqual(parse_duration("45m"), 2700)
        self.assertEqual(parse_duration("45min"), 2700)
        self.assertEqual(parse_duration("-0h15"), -900)
        for bad in ("", "abc", "1x"):
            with self.assertRaises(ValueError):
                parse_duration(bad)

    def test_format_duration(self):
        self.assertEqual(format_duration(3725), "1h 02min")
        self.assertEqual(format_duration(-900), "-0h 15min")

    def test_parse_clock_time_uses_previous_day_when_in_future(self):
        ref = datetime(2026, 9, 30, 9, 0, tzinfo=BRT)
        self.assertEqual(parse_clock_time("08:15", ref), datetime(2026, 9, 30, 8, 15, tzinfo=BRT))
        self.assertEqual(parse_clock_time("18:30", ref), datetime(2026, 9, 29, 18, 30, tzinfo=BRT))
        with self.assertRaises(ValueError):
            parse_clock_time("25:00", ref)

    def test_periods(self):
        now = datetime(2026, 9, 30, 12, 0, tzinfo=BRT)  # quarta
        week = period("semana", now)
        self.assertEqual(week.start, datetime(2026, 9, 28, tzinfo=BRT))   # segunda
        self.assertEqual(week.end, datetime(2026, 10, 5, tzinfo=BRT))
        last_month = period("mes-passado", now)
        self.assertEqual((last_month.start, last_month.end),
                         (datetime(2026, 8, 1, tzinfo=BRT), datetime(2026, 9, 1, tzinfo=BRT)))
        self.assertEqual(period("mes", datetime(2026, 12, 15, tzinfo=BRT)).end, datetime(2027, 1, 1, tzinfo=BRT))


if __name__ == "__main__":
    unittest.main()
