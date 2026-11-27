"""Chọn đường 2PC cho chuyển cơ sở và ánh xạ lỗi của thủ tục (không cần SQL Server; chạy thật nằm ở docs/evidence/scripts/ev_dtx*.py)."""

from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings

from core.academics import transfers
from core.academics.common import AcademicConflict, AcademicInfrastructureUnavailable

SNAPSHOT = {
    "transfer_id": "Q1-CC-000001", "student_id": "Q1-HV-000001", "source_site": "Q1", "target_site": "Q7",
    "status": "dang_xu_ly", "step": "da_tiep_nhan", "full_name": "Nguyễn Văn An", "slug": "nguyen-van-an",
}


class TwoPhaseLinkTests(SimpleTestCase):
    @override_settings(TRANSFER_2PC_LINKED_SERVERS={"Q1": {"Q7": "LS_Q7"}})
    def test_only_configured_pairs_use_two_phase(self):
        self.assertEqual(transfers._two_phase_link("Q1", "Q7"), "LS_Q7")
        self.assertIsNone(transfers._two_phase_link("Q1", "TD"))
        self.assertIsNone(transfers._two_phase_link("Q7", "Q1"))

    @override_settings(TRANSFER_2PC_LINKED_SERVERS={})
    def test_unconfigured_keeps_local_path(self):
        self.assertIsNone(transfers._two_phase_link("Q1", "Q7"))


class TwoPhaseExecutionTests(SimpleTestCase):
    def _patched(self, cursor):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        connection.settings_dict = {"NAME": "QLTTNN_Q7"}
        return patch.object(transfers, "connections", {"site_q1": connection, "site_q7": connection})

    def _run(self, cursor):
        with self._patched(cursor), patch.object(transfers, "get_site_database_alias", side_effect=lambda s: f"site_{s.lower()}"):
            transfers._execute_two_phase(dict(SNAPSHOT), "Q1-TK-000001", "LS_Q7")

    def test_calls_the_procedure_with_transfer_link_and_destination_database(self):
        cursor = MagicMock()
        self._run(cursor)
        sql, params = cursor.execute.call_args[0]
        self.assertIn("sp_chuyen_co_so_2pc", sql)
        self.assertEqual(params[:3], ["Q1-CC-000001", "LS_Q7", "QLTTNN_Q7"])
        self.assertEqual(params[-1], "Q1-TK-000001")

    def test_data_refusal_becomes_conflict_and_keeps_the_message(self):
        cursor = MagicMock()
        cursor.execute.side_effect = DatabaseError(
            "42000", "[42000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Đã tồn tại hồ sơ khác tại cơ sở đích (51519) (SQLExecDirectW)")
        with self.assertRaises(AcademicConflict) as caught:
            self._run(cursor)
        self.assertIn("Đã tồn tại hồ sơ khác", str(caught.exception))

    def test_link_or_dtc_failure_is_infrastructure_and_retryable(self):
        cursor = MagicMock()
        cursor.execute.side_effect = DatabaseError(
            "42000", "[42000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Database 'QLTTNN_Q7' cannot be opened because it is offline. (942)")
        with self.assertRaises(AcademicInfrastructureUnavailable):
            self._run(cursor)

    def test_configuration_error_codes_are_not_treated_as_data_conflicts(self):
        for code in ("51511", "51514", "51520", "51521", "51524", "51525"):
            self.assertNotIn(code, transfers._TWO_PHASE_CONFLICT_CODES)


class ExecuteSelectionTests(SimpleTestCase):
    @override_settings(TRANSFER_2PC_LINKED_SERVERS={"Q1": {"Q7": "LS_Q7"}})
    def test_untouched_transfer_uses_two_phase_and_skips_local_steps(self):
        with patch.object(transfers, "_transfer_snapshot", return_value=dict(SNAPSHOT)), \
                patch.object(transfers, "_active_destination"), \
                patch.object(transfers, "_execute_two_phase") as two_phase, \
                patch.object(transfers, "_create_destination_profile") as local_create:
            result = transfers.execute_approved_transfer.__wrapped__(source_site="Q1", transfer_id="Q1-CC-000001", actor_id="Q1-TK-000001")
        two_phase.assert_called_once()
        local_create.assert_not_called()
        self.assertEqual((result["complete"], result["mechanism"]), (True, "2PC"))

    @override_settings(TRANSFER_2PC_LINKED_SERVERS={"Q1": {"Q7": "LS_Q7"}})
    def test_partly_done_transfer_resumes_on_the_local_path(self):
        snapshot = {**SNAPSHOT, "step": "da_tao_ho_so_dich"}
        with patch.object(transfers, "_transfer_snapshot", return_value=snapshot), \
                patch.object(transfers, "_active_destination"), \
                patch.object(transfers, "_execute_two_phase") as two_phase, \
                patch.object(transfers, "_mark_source_student_transferred") as mark, \
                patch.object(transfers, "_activate_destination"), \
                patch.object(transfers, "_checkpoint_source"):
            result = transfers.execute_approved_transfer.__wrapped__(source_site="Q1", transfer_id="Q1-CC-000001", actor_id="Q1-TK-000001")
        two_phase.assert_not_called()
        mark.assert_called_once()
        self.assertTrue(result["complete"])
        self.assertNotIn("mechanism", result)

    @override_settings(TRANSFER_2PC_LINKED_SERVERS={})
    def test_without_configuration_the_local_path_is_unchanged(self):
        with patch.object(transfers, "_transfer_snapshot", return_value=dict(SNAPSHOT)), \
                patch.object(transfers, "_active_destination"), \
                patch.object(transfers, "_execute_two_phase") as two_phase, \
                patch.object(transfers, "_create_destination_profile") as local_create, \
                patch.object(transfers, "_mark_source_student_transferred"), \
                patch.object(transfers, "_activate_destination"), \
                patch.object(transfers, "_checkpoint_source"):
            transfers.execute_approved_transfer.__wrapped__(source_site="Q1", transfer_id="Q1-CC-000001", actor_id="Q1-TK-000001")
        two_phase.assert_not_called()
        local_create.assert_called_once()
