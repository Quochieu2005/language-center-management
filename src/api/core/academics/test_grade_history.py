from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.academics import grades


class GradeHistoryCountTests(SimpleTestCase):
    def test_count_matches_empty_and_nonempty_history(self):
        for rows in ([], [("LOG-1",), ("LOG-2",)]):
            with self.subTest(rows=rows):
                cursor = MagicMock()
                cursor.__enter__.return_value = cursor
                cursor.description = [("log_id",)]
                cursor.fetchall.return_value = rows
                connection = MagicMock()
                connection.cursor.return_value = cursor
                with (
                    patch.object(grades, "require_active_site", return_value="q1"),
                    patch.object(grades, "connections", {"q1": connection}),
                    patch.object(grades, "_teacher_owns_enrollment", return_value=("DK-1",)),
                ):
                    result = grades.list_grade_history(site_code="Q1", teacher_id="GV-1", enrollment_id="DK-1")
                self.assertEqual(result["count"], len(rows))
                self.assertEqual(result["results"], [{"log_id": row[0]} for row in rows])
