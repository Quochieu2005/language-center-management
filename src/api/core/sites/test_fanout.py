"""Unreachable-site cooldown in the shared read fan-out."""

from django.db import OperationalError, ProgrammingError
from django.test import SimpleTestCase, override_settings

from core.sites import fanout


class UnreachableSiteCooldownTests(SimpleTestCase):
    def setUp(self):
        fanout._unreachable_until.clear()
        self.addCleanup(fanout._unreachable_until.clear)
        self.calls = []

    def _reader(self, failures):
        def read(site):
            self.calls.append(site)
            if site in failures:
                raise failures[site]
            return site.lower()
        return read

    def test_connect_failure_skips_site_until_cooldown_and_keeps_it_missing(self):
        timeout = OperationalError("('08001', 'TCP Provider: The wait operation timed out.')")
        values, errors = fanout.read_sites_concurrently(("Q1", "Q7"), self._reader({"Q7": timeout}))
        self.assertEqual(values, {"Q1": "q1"})
        self.assertIs(errors["Q7"], timeout)

        self.calls.clear()
        values, errors = fanout.read_sites_concurrently(("Q1", "Q7"), self._reader({}))
        self.assertEqual(self.calls, ["Q1"])  # Q7 not contacted again
        self.assertIsInstance(errors["Q7"], fanout.SiteTemporarilyUnreachable)
        self.assertIsInstance(errors["Q7"], OperationalError)  # callers still treat it as DatabaseError
        self.assertEqual(values, {"Q1": "q1"})

    def test_site_is_retried_after_cooldown_and_success_clears_it(self):
        timeout = OperationalError("08001 TCP Provider")
        fanout.read_sites_concurrently(("Q7",), self._reader({"Q7": timeout}))
        fanout._unreachable_until["Q7"] = 0  # cooldown elapsed
        values, errors = fanout.read_sites_concurrently(("Q7",), self._reader({}))
        self.assertEqual((values, errors), ({"Q7": "q7"}, {}))
        self.assertNotIn("Q7", fanout._unreachable_until)

    def test_query_errors_are_not_cached(self):
        fanout.read_sites_concurrently(("Q7",), self._reader({"Q7": ProgrammingError("Invalid object name")}))
        fanout.read_sites_concurrently(("Q7",), self._reader({"Q7": OperationalError("HYT00 query timeout")}))
        self.assertEqual(fanout._unreachable_until, {})

    @override_settings(SITE_UNREACHABLE_COOLDOWN_SECONDS=0)
    def test_zero_cooldown_disables_skip(self):
        fanout.read_sites_concurrently(("Q7",), self._reader({"Q7": OperationalError("08001")}))
        self.assertEqual(fanout._unreachable_until, {})
