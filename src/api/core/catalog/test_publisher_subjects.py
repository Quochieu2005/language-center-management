from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings

from core.catalog import publisher_subjects as writer
from core.catalog.serializers import SharedSubjectPatchSerializer
from core.catalog.services import SharedCatalogConflict, SharedCatalogUnavailable, update_shared_subject
from core.catalog.subject_write_services import create_shared_subject, delete_shared_subject


class Cursor:
    def __init__(self, owner, site):
        self.owner, self.site, self.rows = owner, site, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        state = self.owner.data[self.site]
        self.rows = []
        if sql.startswith("SELECT bang_tac_dong"):
            receipt = state["receipts"].get(params[0])
            self.rows = [receipt] if receipt else []
        elif sql.startswith("SELECT ma_mon"):
            self.rows = [tuple(row[field] for field in writer._FIELDS)
                         for row in state["subjects"].values()
                         if row["ma_mon"] == params[0] or row["slug"] == params[1]]
        elif sql.startswith("SELECT TOP (1) ma_khoa_hoc"):
            self.rows = [("KH-01",)] if params[0] in state["courses"] else []
        else:
            self.owner.writes.append((self.site, sql, params))
            if sql.startswith("INSERT INTO dbo.MonHoc"):
                row = dict(zip(writer._FIELDS, [*params, 1]))
                state["subjects"][row["ma_mon"]] = row
            elif sql.startswith("UPDATE dbo.MonHoc"):
                slug, name, description, record_id, version = params
                row = state["subjects"][record_id]
                if row["phien_ban"] == version:
                    row.update(slug=slug, ten_mon=name, mo_ta=description, phien_ban=version + 1)
            elif sql.startswith("DELETE FROM dbo.MonHoc"):
                del state["subjects"][params[0]]
            elif sql.startswith("INSERT INTO dbo.Logs"):
                key, site, actor, action, record_id, before, payload, target = params
                state["receipts"][key] = ("MonHoc", action, target, "thanh_cong", before, payload)
            else:
                raise AssertionError(sql)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


@override_settings(MONHOC_PUBLISHER_SITE_CODE="Q1", AUTH_SESSION_SITE_CODE="Q7")
class PublisherSubjectTests(SimpleTestCase):
    def setUp(self):
        self.data = {site: {"subjects": {}, "receipts": {}, "courses": set()}
                     for site in ("Q1", "Q7", "TD")}
        self.writes, self.atomics = [], []
        self.after_commit = lambda: None
        self.available, self.missing = ("Q1", "Q7", "TD"), ()
        connections = {site: SimpleNamespace(cursor=lambda site=site: Cursor(self, site)) for site in self.data}
        for patcher in (
            patch.object(writer, "get_site_database_alias", side_effect=lambda site: site),
            patch.object(writer, "get_site_connection", side_effect=lambda site: connections[site]),
            patch.object(writer, "connections", connections),
            patch.object(writer, "acquire_record_lock"),
            patch.object(writer, "active_site_state", side_effect=lambda: (self.available, self.missing)),
            patch.object(writer.transaction, "atomic", side_effect=self.atomic),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    @contextmanager
    def atomic(self, using):
        self.atomics.append(using)
        snapshot = deepcopy(self.data[using])
        try:
            yield
        except Exception:
            self.data[using] = snapshot
            raise
        else:
            if using == "Q1":
                self.after_commit()

    def replicate(self, *sites):
        for site in sites:
            self.data[site]["subjects"] = deepcopy(self.data["Q1"]["subjects"])

    def seed(self):
        self.data["Q1"]["subjects"]["MH-ENG"] = {
            "ma_mon": "MH-ENG", "slug": "tieng-anh", "ten_mon": "Tiếng Anh",
            "mo_ta": None, "phien_ban": 1,
        }
        self.replicate("Q7", "TD")

    def create(self, key="request-0001", name="Tiếng Anh"):
        return create_shared_subject(
            subject={"ma_mon": "MH-ENG", "slug": "tieng-anh", "ten_mon": name, "mo_ta": None},
            idempotency_key=key, actor_id="BIG-01",
        )

    def update(self, name="Tiếng Anh mới", key="update-0001"):
        return update_shared_subject(slug="tieng-anh", patch={"ten_mon": name},
                                     idempotency_key=key, actor_id="BIG-01")

    def delete(self, key="delete-0001"):
        return delete_shared_subject(slug="tieng-anh", idempotency_key=key, actor_id="BIG-01")

    def test_create_writes_only_publisher_even_when_session_site_is_q7(self):
        result = self.create()
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_sites"], ["Q7", "TD"])
        self.assertEqual({site for site, _, _ in self.writes}, {"Q1"})
        self.assertEqual(self.atomics, ["Q1"])
        self.assertEqual(len(self.data["Q1"]["receipts"]), 1)
        self.assertFalse(self.data["Q7"]["receipts"])

    def test_retry_checks_replicas_without_reinserting_or_changing_version(self):
        self.create()
        count = len(self.writes)
        self.replicate("Q7")
        self.assertEqual(self.create()["missing_sites"], ["TD"])
        self.replicate("TD")
        result = self.create()
        self.assertTrue(result["complete"])
        self.assertTrue(result["idempotent_replay"])
        self.assertEqual(len(self.writes), count)
        self.assertEqual(result["phien_ban"], 1)

    def test_changed_body_or_operation_with_same_key_is_rejected(self):
        self.create()
        with self.assertRaises(SharedCatalogConflict):
            self.create(name="Tiếng Nhật")
        with self.assertRaises(SharedCatalogConflict):
            self.update(key="request-0001")

    def test_update_slug_retry_uses_record_id_and_writes_once(self):
        self.seed()
        first = self.update()
        self.assertEqual(first["slug"], "tieng-anh-moi")
        self.assertEqual(first["phien_ban"], 2)
        self.replicate("Q7", "TD")
        count = len(self.writes)
        self.assertTrue(self.update()["complete"])
        self.assertEqual(len(self.writes), count)
        self.assertEqual({site for site, _, _ in self.writes}, {"Q1"})

    def test_replica_check_occurs_after_publisher_commit(self):
        self.seed()
        self.after_commit = lambda: self.replicate("Q7", "TD")
        self.assertTrue(self.update()["complete"])

    def test_outage_after_commit_is_incomplete_and_retry_recovers(self):
        self.seed()
        original = writer.get_site_connection
        def unavailable(site):
            if site == "Q7":
                raise DatabaseError("offline")
            return original(site)
        self.after_commit = lambda: None
        # Site failed after preflight but before post-commit confirmation.
        original_verify = writer._verify
        def verify(*args, **kwargs):
            with patch.object(writer, "get_site_connection", side_effect=unavailable):
                return original_verify(*args, **kwargs)
        with patch.object(writer, "_verify", side_effect=verify):
            result = self.update()
        self.assertEqual(result["missing_sites"], ["Q7", "TD"])
        self.replicate("Q7", "TD")
        self.assertTrue(self.update()["complete"])

    def test_delete_blocks_remote_course_and_only_deletes_publisher_after_clear(self):
        self.seed()
        self.data["Q7"]["courses"].add("MH-ENG")
        with self.assertRaises(SharedCatalogConflict):
            self.delete()
        self.assertFalse(self.writes)
        self.data["Q7"]["courses"].clear()
        self.assertFalse(self.delete()["complete"])
        self.assertEqual({site for site, _, _ in self.writes}, {"Q1"})
        self.replicate("Q7", "TD")
        self.assertTrue(self.delete()["complete"])

    def test_missing_site_blocks_new_write_but_does_not_block_receipt_retry(self):
        self.available, self.missing = ("Q1", "Q7"), ("TD",)
        with self.assertRaises(SharedCatalogUnavailable):
            self.create()
        self.assertFalse(self.writes)
        self.available, self.missing = ("Q1", "Q7", "TD"), ()
        self.create()
        self.replicate("Q7", "TD")
        self.available, self.missing = ("Q1", "Q7"), ("TD",)
        self.assertEqual(self.create()["missing_sites"], ["TD"])

    def test_retry_never_replays_over_a_later_publisher_edit(self):
        self.seed()
        self.update()
        self.data["Q1"]["subjects"]["MH-ENG"]["phien_ban"] += 1
        with self.assertRaises(SharedCatalogConflict):
            self.update()

    def test_failed_receipt_insert_rolls_back_subject_change(self):
        self.seed()
        original = Cursor.execute
        def fail_receipt(cursor, sql, params):
            if sql.startswith("INSERT INTO dbo.Logs"):
                raise DatabaseError("injected ledger failure")
            return original(cursor, sql, params)
        with patch.object(Cursor, "execute", fail_receipt):
            with self.assertRaises(SharedCatalogUnavailable):
                self.update()
        self.assertEqual(self.data["Q1"]["subjects"]["MH-ENG"]["phien_ban"], 1)
        self.assertEqual(self.data["Q1"]["subjects"]["MH-ENG"]["ten_mon"], "Tiếng Anh")
        self.assertFalse(self.data["Q1"]["receipts"])

    def test_retry_from_another_actor_is_rejected(self):
        self.create()
        with self.assertRaises(SharedCatalogConflict):
            writer.write_subject(action="tao", slug="tieng-anh", payload={
                "ma_mon": "MH-ENG", "slug": "tieng-anh", "ten_mon": "Tiếng Anh", "mo_ta": None,
            }, idempotency_key="request-0001", actor_id="OTHER-BIG")

    def test_site_from_request_cannot_override_publisher(self):
        serializer = SharedSubjectPatchSerializer(data={"ten_mon": "English", "site_code": "Q7"})
        self.assertFalse(serializer.is_valid())
