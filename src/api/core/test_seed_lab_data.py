"""The LAB seed must never be able to touch anything that is not tagged LAB."""

from django.test import SimpleTestCase

from core.management.commands.seed_lab_data import (
    CLASSES, ENROLLMENTS, REMOVE_STEPS, STUDENTS, class_pattern, plan_for, student_id,
)


class LabPlanTests(SimpleTestCase):
    def test_every_identifier_in_the_plan_is_tagged_lab_and_site_prefixed(self):
        plan = plan_for("Q7")
        ids = [plan["teacher"], plan["room"], *plan["students"], *plan["classes"]]
        self.assertTrue(all(i.startswith("Q7-") and "-LAB" in i for i in ids), ids)
        self.assertEqual(len(plan["students"]), STUDENTS)
        self.assertEqual(len(plan["classes"]), len(CLASSES))

    def test_enrollments_use_planned_students_and_classes_only(self):
        plan = plan_for("TD")
        self.assertEqual(len(plan["enrollments"]), len(ENROLLMENTS))
        for sid, class_id in plan["enrollments"]:
            self.assertIn(sid, plan["students"])
            self.assertIn(class_id, plan["classes"])

    def test_some_students_and_the_last_seat_class_stay_free_for_the_tests(self):
        plan = plan_for("Q1")
        enrolled = {sid for sid, _ in plan["enrollments"]}
        self.assertGreaterEqual(len(set(plan["students"]) - enrolled), 3)
        self.assertEqual(min(capacity for _tag, capacity, _name in CLASSES), 1)
        self.assertEqual(student_id("Q1", 6), "Q1-HV-LAB06")

    def test_class_pattern_only_matches_lab_classes_of_that_site(self):
        self.assertEqual(class_pattern("Q1"), "Q1-LH-LAB%")

    def test_every_delete_step_is_restricted_to_lab_classes(self):
        # Each predicate is parameterised with the LAB class pattern; no step is an unconditional delete.
        for table, predicate in REMOVE_STEPS:
            self.assertIn("LIKE %s", predicate, table)
            self.assertNotIn("1=1", predicate.replace(" ", ""), table)
