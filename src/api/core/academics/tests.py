from datetime import date

from django.test import SimpleTestCase

from core.academics.common import AcademicInvalid
from core.academics.installment_serializers import TuitionInstallmentPlanWriteSerializer
from core.academics.tuition_installments import (
    ALLOWED_INSTALLMENT_COUNTS,
    add_calendar_months,
    build_installment_amounts,
    build_installment_schedule,
)


class TuitionInstallmentScheduleTests(SimpleTestCase):
    def test_monthly_amounts_split_evenly_and_put_remainder_in_last_month(self):
        self.assertEqual(build_installment_amounts(1000, "monthly", 3), [333, 333, 334])

    def test_calendar_month_dates_clamp_to_month_end_then_recover_original_day(self):
        start = date(2099, 1, 31)
        self.assertEqual(add_calendar_months(start, 1), date(2099, 2, 28))
        self.assertEqual(add_calendar_months(start, 2), date(2099, 3, 31))

    def test_monthly_schedule_total_matches_tuition(self):
        schedule = build_installment_schedule(
            total=1000, payment_mode="monthly", installment_count=3,
            first_due_date=date(2099, 1, 31),
        )
        self.assertEqual([item["amount_due"] for item in schedule], [333, 333, 334])
        self.assertEqual(sum(item["amount_due"] for item in schedule), 1000)
        self.assertEqual(schedule[-1]["due_date"], date(2099, 3, 31))

    def test_full_payment_plan_has_one_installment(self):
        self.assertEqual(build_installment_amounts(1500000, "full", None), [1500000])

    def test_only_three_six_nine_or_twelve_months_are_supported(self):
        self.assertEqual(ALLOWED_INSTALLMENT_COUNTS, (3, 6, 9, 12))
        for count in ALLOWED_INSTALLMENT_COUNTS:
            with self.subTest(allowed_count=count):
                serializer = TuitionInstallmentPlanWriteSerializer(
                    data={
                        "payment_mode": "monthly",
                        "installment_count": count,
                        "first_due_date": "2099-01-05",
                    }
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                amounts = build_installment_amounts(1200, "monthly", count)
                self.assertEqual(len(amounts), count)
                self.assertEqual(sum(amounts), 1200)

        for count in (2, 4, 5, 8, 10, 11, 24):
            with self.subTest(count=count):
                serializer = TuitionInstallmentPlanWriteSerializer(
                    data={
                        "payment_mode": "monthly",
                        "installment_count": count,
                        "first_due_date": "2099-01-05",
                    }
                )
                self.assertFalse(serializer.is_valid())
                self.assertIn("installment_count", serializer.errors)
                with self.assertRaises(AcademicInvalid):
                    build_installment_amounts(1000, "monthly", count)

    def test_monthly_plan_requires_installment_count(self):
        serializer = TuitionInstallmentPlanWriteSerializer(
            data={"payment_mode": "monthly", "first_due_date": "2099-01-05"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("installment_count", serializer.errors)

    def test_full_plan_rejects_month_count(self):
        serializer = TuitionInstallmentPlanWriteSerializer(
            data={
                "payment_mode": "full",
                "installment_count": 3,
                "first_due_date": "2099-01-05",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("installment_count", serializer.errors)

    def test_monthly_plan_validates_future_first_due_date(self):
        serializer = TuitionInstallmentPlanWriteSerializer(
            data={
                "payment_mode": "monthly",
                "installment_count": 6,
                "first_due_date": "2099-01-05",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
