from contextlib import nullcontext
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.catalog import course_services, public_courses, services
from core.catalog.serializers import SharedCourseCreateSerializer, SharedSubjectPatchSerializer
from core.catalog.views import SharedCourseCollectionView, SharedCourseDetailView, SharedSubjectDetailView


def _subject(version=4, *, name="English", description="General English"):
    return {
        "ma_mon": "MH-ENG",
        "slug": "english",
        "ten_mon": name,
        "mo_ta": description,
        "phien_ban": version,
    }


def _event(before, after, request_hash):
    return {"before": before, "after": after, "request_hash": request_hash}


class SharedCatalogReplicationTests(SimpleTestCase):
    def setUp(self):
        self.patchers = [
            patch.object(services, "active_site_state", return_value=(("Q1", "Q7", "TD"), ())),
            patch.object(services, "get_site_database_alias", side_effect=lambda site: f"site_{site.lower()}"),
            patch.object(services, "connections", {"site_q1": SimpleNamespace(cursor=lambda: nullcontext())}),
            patch.object(services, "acquire_record_lock"),
            patch.object(services.transaction, "atomic", side_effect=lambda using: nullcontext()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_first_update_writes_all_active_sites(self, read_site, apply_site):
        before = _subject()
        read_site.side_effect = lambda site, slug, event_id: (before.copy(), None)

        result = services.update_shared_subject(
            slug="english", patch={"ten_mon": "English A1"},
            idempotency_key="request-0001", actor_id="Q1-TK-000001",
        )

        self.assertTrue(result["complete"])
        self.assertEqual(result["phien_ban"], 5)
        self.assertEqual(result["sites"], ["Q1", "Q7", "TD"])
        self.assertEqual(apply_site.call_count, 3)

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_retry_resumes_only_sites_without_ack(self, read_site, apply_site):
        before = _subject()
        after = _subject(5, name="English A1")
        request_hash = services._fingerprint({"ten_mon": "English A1"})
        states = {
            "Q1": (after.copy(), _event(before, after, request_hash)),
            "Q7": (before.copy(), None),
            "TD": (after.copy(), _event(before, after, request_hash)),
        }
        read_site.side_effect = lambda site, slug, event_id: states[site]

        result = services.update_shared_subject(
            slug="english", patch={"ten_mon": "English A1"},
            idempotency_key="request-0001", actor_id="Q1-TK-000001",
        )

        self.assertTrue(result["complete"])
        self.assertTrue(result["idempotent_replay"])
        apply_site.assert_called_once()
        self.assertEqual(apply_site.call_args.kwargs["site_code"], "Q7")

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_retry_with_same_key_and_different_body_is_conflict(self, read_site, apply_site):
        before = _subject()
        after = _subject(5, name="English A1")
        read_site.side_effect = lambda site, slug, event_id: (
            after.copy(), _event(before, after, services._fingerprint({"ten_mon": "English A1"}))
        )

        with self.assertRaises(services.SharedCatalogConflict):
            services.update_shared_subject(
                slug="english", patch={"ten_mon": "English A2"},
                idempotency_key="request-0001", actor_id="Q1-TK-000001",
            )
        apply_site.assert_not_called()

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_remote_write_error_returns_incomplete_retryable_result(self, read_site, apply_site):
        before = _subject()
        read_site.side_effect = lambda site, slug, event_id: (before.copy(), None)

        def fail_q7(**kwargs):
            if kwargs["site_code"] == "Q7":
                raise DatabaseError("injected site write failure")

        apply_site.side_effect = fail_q7
        result = services.update_shared_subject(
            slug="english", patch={"ten_mon": "English A1"},
            idempotency_key="request-0001", actor_id="Q1-TK-000001",
        )

        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_sites"], ["Q7"])
        self.assertIn("Q1", result["sites"])
        self.assertIn("TD", result["sites"])

    def test_patch_rejects_fields_outside_subject_contract(self):
        serializer = SharedSubjectPatchSerializer(
            data={"ten_mon": "English A1", "ma_co_so": "TD", "phien_ban": 99}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"ma_co_so", "phien_ban"})

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(services, "_apply_site")
    @patch.object(services, "_read_site")
    def test_missing_active_site_blocks_all_replication_writes(self, read_site, apply_site):
        with patch.object(services, "active_site_state", return_value=(("Q1", "Q7"), ("TD",))):
            with self.assertRaises(services.SharedCatalogUnavailable) as raised:
                services.update_shared_subject(
                    slug="english", patch={"ten_mon": "English A1"},
                    idempotency_key="request-0001", actor_id="Q1-TK-000001",
                )

        self.assertEqual(raised.exception.missing_sites, ("TD",))
        read_site.assert_not_called()
        apply_site.assert_not_called()


class SharedCatalogPermissionTests(SimpleTestCase):
    def test_only_admin_big_can_write_shared_subjects(self):
        request = APIRequestFactory().patch(
            "/api/v1/admin/shared/subjects/english/",
            {"ten_mon": "English A1"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="request-0001",
        )
        force_authenticate(
            request,
            user=SimpleNamespace(
                is_authenticated=True, pk="Q1-TK-1", role="admin_small", account_id="Q1-TK-1"
            ),
        )
        with patch("core.catalog.views.update_shared_subject") as update:
            response = SharedSubjectDetailView.as_view()(request, slug="english")

        self.assertEqual(response.status_code, 403)
        update.assert_not_called()

class PublicCourseCatalogTests(SimpleTestCase):
    sites = (
        ("Q1", "Cơ sở Quận 1", "hoat_dong"),
        ("Q7", "Cơ sở Quận 7", "hoat_dong"),
        ("TD", "Cơ sở Thủ Đức", "hoat_dong"),
    )
    course = {
        "course_id": "KH-EN-01",
        "slug": "english-a1",
        "subject_id": "MH-ENG",
        "subject_slug": "tieng-anh",
        "subject_name": "Tiếng Anh",
        "name": "Tiếng Anh A1",
        "level": "A1",
        "session_count": 24,
        "standard_fee": 4200000,
        "version": 1,
    }

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(public_courses, "_read_site_snapshot")
    @patch.object(public_courses, "_read_site_catalog", return_value=sites)
    def test_global_list_uses_site_rows_and_only_open_class_sites(self, _catalog, read_snapshot):
        read_snapshot.side_effect = lambda site, _today: (
            self.sites,
            {"KH-EN-01": self.course.copy()},
            {"KH-EN-01": 0 if site == "Q7" else 1},
        )

        result = public_courses.list_public_courses()

        self.assertTrue(result["complete"])
        self.assertEqual(result["scope"], "GLOBAL")
        self.assertEqual(result["results"][0]["name"], "Tiếng Anh A1")
        self.assertEqual(
            [branch["site_code"] for branch in result["results"][0]["branches"]],
            ["Q1", "TD"],
        )

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(public_courses, "_read_site_catalog", return_value=sites)
    @patch.object(public_courses, "_read_site_snapshot")
    def test_unavailable_site_is_reported_without_claiming_complete_data(self, read_snapshot, _catalog):
        def snapshot(site, _today):
            if site == "Q7":
                raise DatabaseError("injected unavailable site")
            return self.sites, {"KH-EN-01": self.course.copy()}, {"KH-EN-01": 1}

        read_snapshot.side_effect = snapshot

        result = public_courses.list_public_courses()

        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_sites"], ["Q7"])
        self.assertEqual(
            [branch["site_code"] for branch in result["results"][0]["branches"]],
            ["Q1", "TD"],
        )


class SharedCourseReplicationTests(SimpleTestCase):
    def setUp(self):
        self.patchers = [
            patch.object(course_services, "active_site_state", return_value=(("Q1", "Q7", "TD"), ())),
            patch.object(course_services, "get_site_database_alias", side_effect=lambda site: f"site_{site.lower()}"),
            patch.object(course_services, "connections", {"site_q1": SimpleNamespace(cursor=lambda: nullcontext())}),
            patch.object(course_services, "acquire_record_lock"),
            patch.object(course_services.transaction, "atomic", side_effect=lambda using: nullcontext()),
            patch.object(course_services, "_check_subject_replicas"),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _course(self, version=1, name="Tiếng Anh A1"):
        return {
            "ma_khoa_hoc": "KH-EN-A1", "slug": "tieng-anh-a1", "ma_mon": "MH-ENG",
            "ten_khoa_hoc": name, "trinh_do": "A1", "so_buoi": 24,
            "hoc_phi_chuan": 4200000, "phien_ban": version,
        }

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(course_services, "_apply_site")
    @patch.object(course_services, "_read_site_course", return_value=(None, None))
    def test_create_replicates_course_and_ack_to_every_active_site(self, _read, apply):
        course = {key: value for key, value in self._course().items() if key != "phien_ban"}

        result = course_services.create_shared_course(
            course=course, idempotency_key="course-create-001", actor_id="Q1-TK-1"
        )

        self.assertTrue(result["complete"])
        self.assertEqual(result["phien_ban"], 1)
        self.assertEqual(result["sites"], ["Q1", "Q7", "TD"])
        self.assertEqual(apply.call_count, 3)
        self.assertTrue(all(call.kwargs["before"] is None for call in apply.call_args_list))

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(course_services, "_apply_site")
    @patch.object(course_services, "_read_site_course")
    def test_create_retry_writes_only_site_without_ack(self, read, apply):
        course = {key: value for key, value in self._course().items() if key != "phien_ban"}
        request_hash = hashlib.sha256(course_services._json({
            "action": "tao", "slug": course["slug"], "payload": course,
        }).encode("utf-8")).hexdigest()
        after = self._course()
        ack = {"record_id": after["ma_khoa_hoc"], "action": "tao", "before": None,
               "after": after, "request_hash": request_hash}
        read.side_effect = lambda site, **_kwargs: (after.copy(), ack) if site in {"Q1", "TD"} else (None, None)

        result = course_services.create_shared_course(
            course=course, idempotency_key="course-create-001", actor_id="Q1-TK-1"
        )

        self.assertTrue(result["complete"])
        self.assertTrue(result["idempotent_replay"])
        apply.assert_called_once()
        self.assertEqual(apply.call_args.kwargs["site"], "Q7")

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(course_services, "_apply_site")
    @patch.object(course_services, "_read_site_course")
    def test_update_increments_version_and_replicates_to_all_sites(self, read, apply):
        before = self._course()
        read.return_value = (before, None)

        result = course_services.update_shared_course(
            slug=before["slug"], patch={"ten_khoa_hoc": "Tiếng Anh A1 mới"},
            idempotency_key="course-update-001", actor_id="Q1-TK-1",
        )

        self.assertTrue(result["complete"])
        self.assertEqual(result["ten_khoa_hoc"], "Tiếng Anh A1 mới")
        self.assertEqual(result["phien_ban"], 2)
        self.assertEqual(apply.call_count, 3)
        self.assertTrue(all(call.kwargs["before"] == before for call in apply.call_args_list))

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(course_services, "_read_site_course", return_value=(None, None))
    @patch.object(course_services, "_apply_site")
    def test_remote_write_failure_returns_retryable_partial_result(self, apply, _read):
        course = {key: value for key, value in self._course().items() if key != "phien_ban"}

        def fail_q7(**kwargs):
            if kwargs["site"] == "Q7":
                raise DatabaseError("injected site failure")

        apply.side_effect = fail_q7
        result = course_services.create_shared_course(
            course=course, idempotency_key="course-create-002", actor_id="Q1-TK-1"
        )

        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_sites"], ["Q7"])
        self.assertEqual(result["sites"], ["Q1", "TD"])

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(course_services, "_delete_course_replicas")
    @patch.object(course_services, "_read_site_course")
    def test_delete_replicates_only_after_matching_catalog_is_found(self, read, delete):
        before = self._course()
        read.return_value = (before, None)

        result = course_services.delete_shared_course(
            slug=before["slug"], idempotency_key="course-delete-001", actor_id="Q1-TK-1"
        )

        self.assertTrue(result["deleted"])
        self.assertTrue(result["complete"])
        self.assertEqual(result["sites"], ["Q1", "Q7", "TD"])
        delete.assert_called_once()
        self.assertEqual(delete.call_args.kwargs["before"], before)

    @override_settings(AUTH_SESSION_SITE_CODE="Q1")
    @patch.object(course_services, "_delete_course_replicas")
    @patch.object(course_services, "_read_site_course")
    def test_delete_retry_resumes_sites_without_ack(self, read, delete):
        before = self._course()
        request_hash = hashlib.sha256(course_services._json({
            "action": "xoa", "slug": before["slug"], "payload": {},
        }).encode("utf-8")).hexdigest()
        ack = {"record_id": before["ma_khoa_hoc"], "action": "xoa", "before": before,
               "after": None, "request_hash": request_hash}
        read.side_effect = lambda site, **_kwargs: (None, ack) if site in {"Q1", "Q7"} else (before, None)

        result = course_services.delete_shared_course(
            slug=before["slug"], idempotency_key="course-delete-001", actor_id="Q1-TK-1"
        )

        self.assertTrue(result["idempotent_replay"])
        self.assertEqual(delete.call_args.kwargs["events"], {"Q1": ack, "Q7": ack, "TD": None})

    def test_delete_replicates_unused_course_and_blocks_referenced_course(self):
        before = self._course()

        class Cursor:
            def __init__(self, site_state):
                self.site_state, self.rows = site_state, []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, sql, _params=None):
                if "FROM dbo.KhoaHoc WITH" in sql:
                    self.rows = [tuple(before[field] for field in (
                        "ma_khoa_hoc", "slug", "ma_mon", "ten_khoa_hoc", "trinh_do",
                        "so_buoi", "hoc_phi_chuan", "phien_ban",
                    ))] if self.site_state["present"] else []
                elif "FROM dbo.LopHoc" in sql:
                    self.rows = [("Q7-LH-1",)] if self.site_state["referenced"] else []
                elif sql.startswith("DELETE FROM dbo.KhoaHoc"):
                    self.site_state["delete_count"] += 1
                    self.site_state["present"] = False
                    self.rows = []
                else:
                    self.rows = []

            def fetchall(self):
                return self.rows

        def create_states(referenced_site=None):
            states = {
                site: {"present": True, "delete_count": 0, "referenced": site == referenced_site}
                for site in ("Q1", "Q7", "TD")
            }
            connections_by_alias = {
                f"site_{site.lower()}": SimpleNamespace(
                    cursor=lambda site_state=site_state: Cursor(site_state)
                )
                for site, site_state in states.items()
            }
            return states, connections_by_alias

        sites = ("Q1", "Q7", "TD")
        event_ids = {site: f"KHDEL-{site}-key" for site in sites}
        states, connections_by_alias = create_states()
        with patch.object(course_services, "connections", connections_by_alias):
            course_services._delete_course_replicas(
                sites=sites, registry_alias="site_q1", before=before,
                events={site: None for site in sites}, event_ids=event_ids,
                request_hash="hash", actor_id="Q1-TK-1",
            )
        self.assertEqual(sum(site_state["delete_count"] for site_state in states.values()), 3)

        states, connections_by_alias = create_states(referenced_site="Q7")
        with patch.object(course_services, "connections", connections_by_alias):
            with self.assertRaises(course_services.SharedCatalogConflict):
                course_services._delete_course_replicas(
                    sites=sites, registry_alias="site_q1", before=before,
                    events={site: None for site in sites}, event_ids=event_ids,
                    request_hash="hash", actor_id="Q1-TK-1",
                )

        self.assertEqual(sum(site_state["delete_count"] for site_state in states.values()), 0)

    def test_only_admin_big_can_delete_shared_courses(self):
        request = APIRequestFactory().delete(
            "/api/v1/admin/courses/tieng-anh-a1/", HTTP_IDEMPOTENCY_KEY="course-delete-001"
        )
        force_authenticate(request, user=SimpleNamespace(
            is_authenticated=True, pk="Q1-TK-1", role="admin_small", account_id="Q1-TK-1"
        ))
        with patch("core.catalog.views.delete_shared_course") as delete:
            response = SharedCourseDetailView.as_view()(request, slug="tieng-anh-a1")

        self.assertEqual(response.status_code, 403)
        delete.assert_not_called()

    def test_create_serializer_derives_slug_and_rejects_unknown_fields(self):
        payload = {
            "ma_khoa_hoc": "KH-EN-A1", "ma_mon": "MH-ENG", "ten_khoa_hoc": "Tiếng Anh A1",
            "trinh_do": "A1", "so_buoi": 24, "hoc_phi_chuan": 4200000,
        }
        serializer = SharedCourseCreateSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["slug"], "tieng-anh-a1")

        serializer = SharedCourseCreateSerializer(data={**payload, "is_active": True})

        self.assertFalse(serializer.is_valid())
        self.assertIn("is_active", serializer.errors)

    def test_only_admin_big_can_create_shared_courses(self):
        request = APIRequestFactory().post(
            "/api/v1/admin/courses/", {"ma_khoa_hoc": "KH-EN-A1"},
            format="json", HTTP_IDEMPOTENCY_KEY="course-create-001",
        )
        force_authenticate(request, user=SimpleNamespace(
            is_authenticated=True, pk="Q1-TK-1", role="admin_small", account_id="Q1-TK-1"
        ))
        with patch("core.catalog.views.create_shared_course") as create:
            response = SharedCourseCollectionView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        create.assert_not_called()
