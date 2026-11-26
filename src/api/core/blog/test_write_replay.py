"""Replaying a queued Blog write: only a site still owed the operation must still match its ``before`` state."""

from django.test import SimpleTestCase

from core.blog.write_services import sites_off_ack

ORIGINAL = {"title": "gốc"}
EDIT1 = {"title": "sửa 1"}
EDIT2 = {"title": "sửa 2"}


class SitesOffAckTests(SimpleTestCase):
    def test_a_site_that_already_moved_on_through_a_later_edit_is_not_flagged(self):
        # Edit 1 was ACKed at A, which then took edit 2; B was offline and still holds the original.
        flagged = sites_off_ack(
            ("A", "B"), events={"A": {"ack": 1}, "B": None},
            current={"A": EDIT2, "B": ORIGINAL}, before=ORIGINAL, after=EDIT1,
        )
        self.assertEqual(flagged, ())

    def test_a_site_still_owed_the_edit_must_hold_the_before_state(self):
        flagged = sites_off_ack(
            ("A", "B"), events={"A": {"ack": 1}, "B": None},
            current={"A": EDIT1, "B": EDIT2}, before=ORIGINAL, after=EDIT1,
        )
        self.assertEqual(flagged, ("B",))

    def test_second_edit_replay_expects_the_state_the_first_replay_left(self):
        # After edit 1 was replayed at B, edit 2 (before=EDIT1) is expected there.
        self.assertEqual(
            sites_off_ack(("A", "B"), {"A": {"ack": 2}, "B": None}, {"A": EDIT2, "B": EDIT1}, EDIT1, EDIT2), (),
        )
        # If the first replay never happened, B is still at the original and edit 2 must wait.
        self.assertEqual(
            sites_off_ack(("A", "B"), {"A": {"ack": 2}, "B": None}, {"A": EDIT2, "B": ORIGINAL}, EDIT1, EDIT2), ("B",),
        )

    def test_create_replay_expects_no_row_at_a_site_still_owed_it(self):
        self.assertEqual(sites_off_ack(("B",), {"B": None}, {"B": None}, None, {"slug": "x"}), ())
        self.assertEqual(sites_off_ack(("B",), {"B": None}, {"B": {"slug": "x"}}, None, {"slug": "x"}), ("B",))
