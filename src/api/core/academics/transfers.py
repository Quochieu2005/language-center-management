"""Two-step transfer requests and resumable source/destination coordination."""

from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from core.academics.common import (
    AcademicConflict,
    AcademicForbidden,
    AcademicInfrastructureUnavailable,
    AcademicInvalid,
    AcademicNotFound,
    AcademicSiteUnavailable,
    acquire_record_lock,
    active_site_state,
    append_audit,
    next_id,
    require_active_site,
    translate_database_errors,
)
from core.sites.connections import get_site_database_alias


def _rows(cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _append_event(
    cursor, *, site_code: str, transfer_id: str, student_id: str,
    source_site: str, target_site: str, event: str, actor_id: str | None,
    detail: str | None = None,
) -> None:
    cursor.execute(
        """
        SELECT TOP (1) 1 FROM dbo.LichSuChuyenCoSo WITH (UPDLOCK, HOLDLOCK)
        WHERE ma_chuyen = %s AND site_ghi = %s AND su_kien = %s
        """,
        [transfer_id, site_code, event],
    )
    if cursor.fetchone() is not None:
        return
    event_id = next_id(cursor, site_code, "transfer_event")
    cursor.execute(
        """
        INSERT INTO dbo.LichSuChuyenCoSo
            (ma_su_kien, ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich,
             site_ghi, su_kien, ma_tai_khoan_thuc_hien, chi_tiet)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [event_id, transfer_id, student_id, source_site, target_site,
         site_code, event, actor_id, (detail or "")[:1000] or None],
    )


def _audit_transfer(
    cursor, *, site_code: str, actor_id: str | None, action: str,
    transfer_id: str, before: dict | None = None, after: dict | None = None,
) -> None:
    append_audit(
        cursor, site_code=site_code, actor_id=actor_id, action=action,
        table_name="GiaoDichChuyenCoSo", record_id=transfer_id,
        before=before, after=after,
    )


def _active_destination(source_site: str, target_site: str) -> None:
    target = str(target_site or "").strip().upper()
    if target == source_site:
        raise AcademicInvalid("Cơ sở đích phải khác cơ sở nguồn.")
    available, _missing = active_site_state()
    if target not in available:
        raise AcademicSiteUnavailable


@translate_database_errors
def create_transfer_request(
    *, source_site: str, student_slug: str, target_site: str,
    actor_id: str, remote_ip: str, reason: str,
) -> dict[str, Any]:
    source_site = str(source_site).strip().upper()
    target_site = str(target_site).strip().upper()
    require_active_site(source_site)
    _active_destination(source_site, target_site)
    alias = get_site_database_alias(source_site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT ma_hoc_vien, ma_co_so, trang_thai, ho_ten "
                "FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK) WHERE slug = %s AND ma_co_so = %s",
                [student_slug, source_site],
            )
            student = cursor.fetchone()
            if student is None:
                raise AcademicNotFound
            student_id = str(student[0])
            if str(student[2]).lower() != "dang_hoc":
                raise AcademicConflict("Chỉ học viên đang học tại cơ sở nguồn mới được đề nghị chuyển.")
            acquire_record_lock(cursor, f"student-transfer:{source_site}:{student_id}")
            cursor.execute(
                """
                SELECT TOP (1) 1
                FROM dbo.DangKy AS d
                INNER JOIN dbo.HocPhi AS hp
                    ON hp.ma_dang_ky = d.ma_dang_ky AND hp.ma_co_so = d.ma_co_so
                WHERE d.ma_co_so = %s AND d.ma_hoc_vien = %s
                  AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
                  AND hp.so_tien_phai_dong - hp.giam_gia - hp.so_tien_da_dong > 0
                """,
                [source_site, student_id],
            )
            if cursor.fetchone() is not None:
                raise AcademicConflict("Học viên còn công nợ học phí tại cơ sở nguồn.")
            cursor.execute(
                """
                SELECT TOP (1) ma_chuyen
                FROM dbo.GiaoDichChuyenCoSo WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_hoc_vien = %s AND co_so_nguon = %s
                  AND trang_thai IN ('cho_duyet', 'dang_xu_ly')
                """,
                [student_id, source_site],
            )
            if cursor.fetchone() is not None:
                raise AcademicConflict("Học viên đã có đề nghị chuyển cơ sở đang mở.")

            transfer_id = next_id(cursor, source_site, "transfer")
            cursor.execute(
                """
                INSERT INTO dbo.GiaoDichChuyenCoSo
                    (ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich,
                     ma_tai_khoan_de_nghi, ly_do_de_nghi)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [transfer_id, student_id, source_site, target_site, actor_id, reason],
            )
            _append_event(
                cursor, site_code=source_site, transfer_id=transfer_id,
                student_id=student_id, source_site=source_site, target_site=target_site,
                event="de_nghi", actor_id=actor_id, detail=reason,
            )
            _audit_transfer(
                cursor, site_code=source_site, actor_id=actor_id,
                action="tao_de_nghi_chuyen_co_so", transfer_id=transfer_id,
                after={"student_id": student_id, "target_site": target_site, "status": "cho_duyet"},
            )
    return {
        "transfer_id": transfer_id, "student_id": student_id,
        "student_name": str(student[3]), "source_site": source_site,
        "target_site": target_site, "status": "cho_duyet", "step": "cho_duyet",
    }


def _list_site_transfers(site_code: str, *, status_filter: str | None, take: int) -> tuple[int, list[dict[str, Any]]]:
    alias = require_active_site(site_code)
    where = "g.co_so_nguon = %s"
    params: list[Any] = [site_code]
    if status_filter:
        where += " AND g.trang_thai = %s"
        params.append(status_filter)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT_BIG(*) FROM dbo.GiaoDichChuyenCoSo AS g WHERE {where}", params
        )
        count = int(cursor.fetchone()[0])
        cursor.execute(
            f"""
            SELECT g.ma_chuyen AS transfer_id, g.ma_hoc_vien AS student_id,
                   h.slug AS student_slug, h.ho_ten AS student_name,
                   g.co_so_nguon AS source_site, g.co_so_dich AS target_site,
                   g.trang_thai AS status, g.buoc_cuoi AS step,
                   g.ma_tai_khoan_de_nghi AS requested_by,
                   g.ma_tai_khoan_quyet_dinh AS decided_by,
                   g.ly_do_de_nghi AS reason, g.ly_do_tu_choi AS rejection_reason,
                   g.ngay_tao AS created_at, g.ngay_quyet_dinh AS decided_at,
                   g.cap_nhat_luc AS updated_at,
                   CASE WHEN g.loi_cuoi IS NULL THEN NULL
                        ELSE N'Một bước chưa hoàn tất; hãy kiểm tra site và retry/đối soát.'
                   END AS last_error
            FROM dbo.GiaoDichChuyenCoSo AS g
            INNER JOIN dbo.HocVien AS h
                ON h.ma_hoc_vien = g.ma_hoc_vien AND h.ma_co_so = g.co_so_nguon
            WHERE {where}
            ORDER BY g.ngay_tao DESC, g.ma_chuyen DESC
            OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY
            """,
            [*params, take],
        )
        return count, _rows(cursor)


@translate_database_errors
def list_transfer_requests(
    *, role: str, user_site: str | None, requested_site: str | None,
    status_filter: str | None, limit: int, offset: int,
) -> dict[str, Any]:
    if role == "admin_small":
        if requested_site:
            raise AcademicForbidden
        sites = (str(user_site or "").strip().upper(),)
        missing: tuple[str, ...] = ()
    elif role == "admin_big":
        if requested_site:
            site = str(requested_site).strip().upper()
            require_active_site(site)
            sites, missing = (site,), ()
        else:
            sites, missing = active_site_state()
    else:
        raise AcademicForbidden
    if not sites or not all(sites):
        raise AcademicSiteUnavailable
    take = offset + limit
    results: list[dict[str, Any]] = []
    counts = 0
    unavailable = list(missing)
    for site in sites:
        try:
            count, items = _list_site_transfers(site, status_filter=status_filter, take=take)
            counts += count
            results.extend(items)
        except AcademicInfrastructureUnavailable:
            unavailable.append(site)
    results.sort(key=lambda item: (item["created_at"], item["source_site"], item["transfer_id"]), reverse=True)
    return {
        "complete": not unavailable,
        "missing_sites": sorted(set(unavailable)),
        "site_codes": list(sites), "count": counts,
        "limit": limit, "offset": offset,
        "results": results[offset:offset + limit],
    }


@translate_database_errors
def decide_transfer(
    *, source_site: str, transfer_id: str, actor_id: str,
    decision: str, reason: str | None,
) -> dict[str, Any]:
    source_site = str(source_site).strip().upper()
    if decision not in {"approve", "reject"}:
        raise AcademicInvalid("Quyết định chỉ được là duyệt hoặc từ chối.")
    if decision == "reject" and not str(reason or "").strip():
        raise AcademicInvalid("Cần nêu lý do từ chối.")
    source_alias = require_active_site(source_site)
    if decision == "approve":
        with connections[source_alias].cursor() as cursor:
            cursor.execute(
                "SELECT co_so_dich FROM dbo.GiaoDichChuyenCoSo WHERE ma_chuyen = %s AND co_so_nguon = %s",
                [transfer_id, source_site],
            )
            row = cursor.fetchone()
        if row is None:
            raise AcademicNotFound
        _active_destination(source_site, str(row[0]))

    with transaction.atomic(using=source_alias):
        with connections[source_alias].cursor() as cursor:
            acquire_record_lock(cursor, f"transfer:{source_site}:{transfer_id}")
            cursor.execute(
                """
                SELECT ma_hoc_vien, co_so_nguon, co_so_dich, trang_thai,
                       buoc_cuoi, ly_do_de_nghi, ly_do_tu_choi
                FROM dbo.GiaoDichChuyenCoSo WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_chuyen = %s AND co_so_nguon = %s
                """,
                [transfer_id, source_site],
            )
            row = cursor.fetchone()
            if row is None:
                raise AcademicNotFound
            student_id, source, target = str(row[0]), str(row[1]), str(row[2])
            current_status, current_step = str(row[3]), str(row[4])
            if current_status in {"dang_xu_ly", "hoan_tat"} and decision == "approve":
                pass
            elif current_status == "tu_choi" and decision == "reject" and str(row[6] or "") == str(reason or ""):
                return {
                    "transfer_id": transfer_id, "status": "tu_choi",
                    "step": "tu_choi", "complete": True,
                }
            elif current_status != "cho_duyet":
                raise AcademicConflict("Đề nghị đã được quyết định hoặc không còn ở trạng thái chờ duyệt.")
            elif decision == "approve":
                cursor.execute(
                    "SELECT trang_thai FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_hoc_vien = %s AND ma_co_so = %s",
                    [student_id, source_site],
                )
                student = cursor.fetchone()
                if student is None:
                    raise AcademicNotFound
                if str(student[0]).lower() != "dang_hoc":
                    raise AcademicConflict("Học viên không còn ở trạng thái đang học tại cơ sở nguồn.")
                cursor.execute(
                    """
                    SELECT TOP (1) 1
                    FROM dbo.DangKy AS d WITH (UPDLOCK, HOLDLOCK)
                    INNER JOIN dbo.HocPhi AS hp
                        ON hp.ma_dang_ky = d.ma_dang_ky AND hp.ma_co_so = d.ma_co_so
                    WHERE d.ma_co_so = %s AND d.ma_hoc_vien = %s
                      AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
                      AND hp.so_tien_phai_dong - hp.giam_gia - hp.so_tien_da_dong > 0
                    """,
                    [source_site, student_id],
                )
                if cursor.fetchone() is not None:
                    raise AcademicConflict("Học viên còn công nợ học phí; không thể duyệt chuyển cơ sở.")
                cursor.execute(
                    """
                    UPDATE dbo.GiaoDichChuyenCoSo
                    SET trang_thai = 'dang_xu_ly', buoc_cuoi = 'da_tiep_nhan',
                        ma_tai_khoan_quyet_dinh = %s, ngay_quyet_dinh = SYSUTCDATETIME(),
                        cap_nhat_luc = SYSUTCDATETIME(), ly_do_tu_choi = NULL
                    WHERE ma_chuyen = %s AND trang_thai = 'cho_duyet'
                    """,
                    [actor_id, transfer_id],
                )
                if cursor.rowcount != 1:
                    raise AcademicConflict("Đề nghị vừa được xử lý bởi một yêu cầu khác.")
                _append_event(
                    cursor, site_code=source_site, transfer_id=transfer_id,
                    student_id=student_id, source_site=source, target_site=target,
                    event="duyet", actor_id=actor_id,
                )
                _audit_transfer(
                    cursor, site_code=source_site, actor_id=actor_id,
                    action="duyet_chuyen_co_so", transfer_id=transfer_id,
                    before={"status": "cho_duyet"}, after={"status": "dang_xu_ly", "step": "da_tiep_nhan"},
                )
            elif decision == "reject":
                if not reason:
                    raise AcademicInvalid("Cần nêu lý do từ chối.")
                cursor.execute(
                    """
                    UPDATE dbo.GiaoDichChuyenCoSo
                    SET trang_thai = 'tu_choi', buoc_cuoi = 'tu_choi',
                        ma_tai_khoan_quyet_dinh = %s, ly_do_tu_choi = %s,
                        ngay_quyet_dinh = SYSUTCDATETIME(), cap_nhat_luc = SYSUTCDATETIME()
                    WHERE ma_chuyen = %s AND trang_thai = 'cho_duyet'
                    """,
                    [actor_id, reason, transfer_id],
                )
                if cursor.rowcount != 1:
                    raise AcademicConflict("Đề nghị vừa được xử lý bởi một yêu cầu khác.")
                _append_event(
                    cursor, site_code=source_site, transfer_id=transfer_id,
                    student_id=student_id, source_site=source, target_site=target,
                    event="tu_choi", actor_id=actor_id, detail=reason,
                )
                _audit_transfer(
                    cursor, site_code=source_site, actor_id=actor_id,
                    action="tu_choi_chuyen_co_so", transfer_id=transfer_id,
                    before={"status": "cho_duyet"}, after={"status": "tu_choi", "reason": reason},
                )
                return {"transfer_id": transfer_id, "status": "tu_choi", "step": "tu_choi", "complete": True}
    return {
        "transfer_id": transfer_id, "status": "dang_xu_ly",
        "step": "da_tiep_nhan", "complete": False,
        "source_site": source_site, "target_site": target,
    }


def _transfer_snapshot(source_site: str, transfer_id: str) -> dict[str, Any]:
    alias = require_active_site(source_site)
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT g.ma_chuyen, g.ma_hoc_vien, g.co_so_nguon, g.co_so_dich,
                   g.trang_thai, g.buoc_cuoi, g.ma_tai_khoan_quyet_dinh,
                   h.slug, h.co_so_goc, h.ma_tai_khoan, h.ho_ten, h.ngay_sinh,
                   h.gioi_tinh, h.sdt, h.email, h.dia_chi, h.ngay_nhap_hoc, h.trang_thai
            FROM dbo.GiaoDichChuyenCoSo AS g
            INNER JOIN dbo.HocVien AS h
                ON h.ma_hoc_vien = g.ma_hoc_vien AND h.ma_co_so = g.co_so_nguon
            WHERE g.ma_chuyen = %s AND g.co_so_nguon = %s
            """,
            [transfer_id, source_site],
        )
        row = cursor.fetchone()
    if row is None:
        raise AcademicNotFound
    keys = (
        "transfer_id", "student_id", "source_site", "target_site", "status", "step",
        "decided_by", "slug", "origin_site", "account_id", "full_name", "birth_date",
        "gender", "phone", "email", "address", "enrolled_on", "student_status",
    )
    return dict(zip(keys, row))


def _create_destination_profile(snapshot: dict[str, Any], actor_id: str) -> None:
    target_site = str(snapshot["target_site"])
    target_alias = require_active_site(target_site)
    with transaction.atomic(using=target_alias):
        with connections[target_alias].cursor() as cursor:
            acquire_record_lock(cursor, f"transfer-destination:{target_site}:{snapshot['transfer_id']}")
            cursor.execute(
                """
                SELECT ma_su_kien FROM dbo.LichSuChuyenCoSo WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_chuyen = %s AND site_ghi = %s AND su_kien = 'tao_ho_so_dich'
                """,
                [snapshot["transfer_id"], target_site],
            )
            event_exists = cursor.fetchone() is not None
            cursor.execute(
                """
                SELECT slug, co_so_goc, ma_tai_khoan, ho_ten, ngay_sinh, gioi_tinh,
                       sdt, email, dia_chi, ngay_nhap_hoc, trang_thai
                FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_hoc_vien = %s AND ma_co_so = %s
                """,
                [snapshot["student_id"], target_site],
            )
            current = cursor.fetchone()
            created = current is None
            expected = (
                snapshot["slug"], snapshot["origin_site"], snapshot["account_id"],
                snapshot["full_name"], snapshot["birth_date"], snapshot["gender"],
                snapshot["phone"], snapshot["email"], snapshot["address"],
                snapshot["enrolled_on"],
            )
            if current is None:
                if event_exists:
                    raise AcademicConflict("Sự kiện đã tồn tại nhưng thiếu hồ sơ đích; cần đối soát.")
                cursor.execute(
                    """
                    INSERT INTO dbo.HocVien
                        (ma_hoc_vien, slug, ma_co_so, co_so_goc, ma_tai_khoan, ho_ten,
                         ngay_sinh, gioi_tinh, sdt, email, dia_chi, ngay_nhap_hoc, trang_thai)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'bao_luu')
                    """,
                    [snapshot["student_id"], snapshot["slug"], target_site,
                     snapshot["origin_site"], snapshot["account_id"], snapshot["full_name"],
                     snapshot["birth_date"], snapshot["gender"], snapshot["phone"],
                     snapshot["email"], snapshot["address"], snapshot["enrolled_on"]],
                )
            else:
                actual = tuple(current[:-1])
                if not event_exists or actual != expected or str(current[-1]).lower() not in {"bao_luu", "dang_hoc"}:
                    raise AcademicConflict("Đã tồn tại hồ sơ khác tại cơ sở đích; cần đối soát trước khi chuyển.")
            _append_event(
                cursor, site_code=target_site, transfer_id=str(snapshot["transfer_id"]),
                student_id=str(snapshot["student_id"]), source_site=str(snapshot["source_site"]),
                target_site=target_site, event="tao_ho_so_dich", actor_id=actor_id,
            )
            if created:
                _audit_transfer(
                    cursor, site_code=target_site, actor_id=actor_id,
                    action="tao_ho_so_hoc_vien_chuyen_den", transfer_id=str(snapshot["transfer_id"]),
                    after={"student_id": snapshot["student_id"], "status": "bao_luu"},
                )


def _checkpoint_source(snapshot: dict[str, Any], actor_id: str, step: str, status: str | None = None) -> None:
    source_site = str(snapshot["source_site"])
    alias = get_site_database_alias(source_site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT ma_hoc_vien, co_so_dich, trang_thai, buoc_cuoi "
                "FROM dbo.GiaoDichChuyenCoSo WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_chuyen = %s AND co_so_nguon = %s",
                [snapshot["transfer_id"], source_site],
            )
            row = cursor.fetchone()
            if row is None:
                raise AcademicNotFound
            current_step = str(row[3])
            step_order = {"da_tiep_nhan": 1, "da_tao_ho_so_dich": 2, "da_cap_nhat_nguon": 3, "hoan_tat": 4}
            if step_order.get(current_step, 0) > step_order.get(step, 0):
                return
            if current_step == step:
                return
            cursor.execute(
                """
                UPDATE dbo.GiaoDichChuyenCoSo
                SET buoc_cuoi = %s, trang_thai = COALESCE(%s, trang_thai),
                    cap_nhat_luc = SYSUTCDATETIME(), loi_cuoi = NULL
                WHERE ma_chuyen = %s AND co_so_nguon = %s
                """,
                [step, status, snapshot["transfer_id"], source_site],
            )
            if step == "da_tao_ho_so_dich":
                _append_event(
                    cursor, site_code=source_site, transfer_id=str(snapshot["transfer_id"]),
                    student_id=str(row[0]), source_site=source_site, target_site=str(row[1]),
                    event="xac_nhan_ho_so_dich", actor_id=actor_id,
                )
            elif step == "hoan_tat":
                _append_event(
                    cursor, site_code=source_site, transfer_id=str(snapshot["transfer_id"]),
                    student_id=str(row[0]), source_site=source_site, target_site=str(row[1]),
                    event="hoan_tat", actor_id=actor_id,
                )
            _audit_transfer(
                cursor, site_code=source_site, actor_id=actor_id,
                action="cap_nhat_tien_trinh_chuyen_co_so", transfer_id=str(snapshot["transfer_id"]),
                before={"step": current_step}, after={"step": step, "status": status or str(row[2])},
            )


def _mark_source_student_transferred(snapshot: dict[str, Any], actor_id: str) -> None:
    source_site = str(snapshot["source_site"])
    alias = get_site_database_alias(source_site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            acquire_record_lock(cursor, f"student-transfer:{source_site}:{snapshot['student_id']}")
            cursor.execute(
                "SELECT trang_thai, buoc_cuoi FROM dbo.GiaoDichChuyenCoSo WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_chuyen = %s AND co_so_nguon = %s",
                [snapshot["transfer_id"], source_site],
            )
            transfer = cursor.fetchone()
            if transfer is None:
                raise AcademicNotFound
            cursor.execute(
                "SELECT trang_thai FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_hoc_vien = %s AND ma_co_so = %s",
                [snapshot["student_id"], source_site],
            )
            student = cursor.fetchone()
            if student is None:
                raise AcademicNotFound
            if str(student[0]).lower() == "da_chuyen_di":
                if str(transfer[0]).lower() in {"dang_xu_ly", "hoan_tat"} and str(transfer[1]).lower() in {
                    "da_cap_nhat_nguon", "hoan_tat",
                }:
                    return
                raise AcademicConflict("Hồ sơ nguồn đã chuyển nhưng tiến trình chưa ghi nhận mốc tương ứng; cần đối soát.")
            if str(student[0]).lower() != "dang_hoc":
                raise AcademicConflict("Hồ sơ nguồn không còn ở trạng thái đang học.")
            if str(transfer[0]).lower() != "dang_xu_ly" or str(transfer[1]).lower() not in {
                "da_tao_ho_so_dich", "da_cap_nhat_nguon",
            }:
                raise AcademicConflict("Giao dịch chưa ở đúng mốc để cập nhật hồ sơ nguồn.")

            cursor.execute(
                """
                SELECT d.ma_lop, COUNT_BIG(*)
                FROM dbo.DangKy AS d WITH (UPDLOCK, HOLDLOCK)
                WHERE d.ma_co_so = %s AND d.ma_hoc_vien = %s
                  AND d.trang_thai IN ('da_dang_ky', 'dang_hoc')
                GROUP BY d.ma_lop
                ORDER BY d.ma_lop
                """,
                [source_site, snapshot["student_id"]],
            )
            class_counts = cursor.fetchall()
            for class_id, count in class_counts:
                cursor.execute(
                    "SELECT si_so_hien_tai FROM dbo.LopHoc WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_co_so = %s AND ma_lop = %s",
                    [source_site, str(class_id)],
                )
                class_row = cursor.fetchone()
                if class_row is None:
                    raise AcademicConflict("Không tìm thấy lớp nguồn để đối soát sĩ số.")
                stored_count = int(class_row[0])
                cursor.execute(
                    "SELECT COUNT_BIG(*) FROM dbo.DangKy WITH (UPDLOCK, HOLDLOCK) "
                    "WHERE ma_co_so = %s AND ma_lop = %s AND trang_thai IN ('da_dang_ky', 'dang_hoc')",
                    [source_site, str(class_id)],
                )
                actual_count = int(cursor.fetchone()[0])
                if stored_count != actual_count:
                    raise AcademicConflict("Sĩ số lưu trong lớp không khớp số đăng ký còn hiệu lực; cần đối soát.")
                cursor.execute(
                    """
                    UPDATE dbo.LopHoc WITH (UPDLOCK, HOLDLOCK)
                    SET si_so_hien_tai = si_so_hien_tai - %s
                    WHERE ma_co_so = %s AND ma_lop = %s AND si_so_hien_tai = %s
                      AND si_so_hien_tai >= %s
                    """,
                    [int(count), source_site, str(class_id), stored_count, int(count)],
                )
                if cursor.rowcount != 1:
                    raise AcademicConflict("Sĩ số lớp nguồn không khớp; cần đối soát trước khi chuyển.")
            cursor.execute(
                """
                UPDATE dbo.DangKy SET trang_thai = 'chuyen_di'
                WHERE ma_co_so = %s AND ma_hoc_vien = %s
                  AND trang_thai IN ('da_dang_ky', 'dang_hoc')
                """,
                [source_site, snapshot["student_id"]],
            )
            cursor.execute(
                "UPDATE dbo.HocVien SET trang_thai = 'da_chuyen_di' "
                "WHERE ma_co_so = %s AND ma_hoc_vien = %s AND trang_thai = 'dang_hoc'",
                [source_site, snapshot["student_id"]],
            )
            if cursor.rowcount != 1:
                raise AcademicConflict("Hồ sơ nguồn vừa thay đổi; giao dịch đã được rollback.")
            _append_event(
                cursor, site_code=source_site, transfer_id=str(snapshot["transfer_id"]),
                student_id=str(snapshot["student_id"]), source_site=source_site,
                target_site=str(snapshot["target_site"]), event="cap_nhat_ho_so_nguon",
                actor_id=actor_id,
            )
            _audit_transfer(
                cursor, site_code=source_site, actor_id=actor_id,
                action="danh_dau_hoc_vien_da_chuyen_di", transfer_id=str(snapshot["transfer_id"]),
                before={"student_status": "dang_hoc"},
                after={"student_status": "da_chuyen_di", "enrollments": "chuyen_di"},
            )
            cursor.execute(
                """
                UPDATE dbo.GiaoDichChuyenCoSo
                SET buoc_cuoi = 'da_cap_nhat_nguon', cap_nhat_luc = SYSUTCDATETIME(), loi_cuoi = NULL
                WHERE ma_chuyen = %s AND co_so_nguon = %s AND trang_thai = 'dang_xu_ly'
                """,
                [snapshot["transfer_id"], source_site],
            )


def _activate_destination(snapshot: dict[str, Any], actor_id: str) -> None:
    target_site = str(snapshot["target_site"])
    alias = require_active_site(target_site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT trang_thai FROM dbo.HocVien WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_hoc_vien = %s AND ma_co_so = %s",
                [snapshot["student_id"], target_site],
            )
            student = cursor.fetchone()
            if student is None:
                raise AcademicConflict("Chưa có hồ sơ đích để kích hoạt.")
            status = str(student[0]).lower()
            if status == "bao_luu":
                cursor.execute(
                    "UPDATE dbo.HocVien SET trang_thai = 'dang_hoc' "
                    "WHERE ma_hoc_vien = %s AND ma_co_so = %s AND trang_thai = 'bao_luu'",
                    [snapshot["student_id"], target_site],
                )
                if cursor.rowcount != 1:
                    raise AcademicConflict("Hồ sơ đích vừa thay đổi; hãy retry giao dịch.")
                activated = True
            elif status != "dang_hoc":
                raise AcademicConflict("Hồ sơ đích có trạng thái không thể kích hoạt.")
            else:
                activated = False
            _append_event(
                cursor, site_code=target_site, transfer_id=str(snapshot["transfer_id"]),
                student_id=str(snapshot["student_id"]), source_site=str(snapshot["source_site"]),
                target_site=target_site, event="hoan_tat", actor_id=actor_id,
            )
            if activated:
                _audit_transfer(
                    cursor, site_code=target_site, actor_id=actor_id,
                    action="kich_hoat_hoc_vien_tai_co_so_dich", transfer_id=str(snapshot["transfer_id"]),
                    before={"student_status": "bao_luu"},
                    after={"student_id": snapshot["student_id"], "student_status": "dang_hoc"},
                )


def _record_retryable_transfer_error(source_site: str, transfer_id: str, actor_id: str) -> None:
    alias = require_active_site(source_site)
    safe_message = "Một site hoặc bước điều phối chưa sẵn sàng; giao dịch được giữ để retry/đối soát."
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT ma_hoc_vien, co_so_dich, trang_thai, loi_cuoi
                FROM dbo.GiaoDichChuyenCoSo WITH (UPDLOCK, HOLDLOCK)
                WHERE ma_chuyen = %s AND co_so_nguon = %s
                """,
                [transfer_id, source_site],
            )
            row = cursor.fetchone()
            if row is None or str(row[2]).lower() != "dang_xu_ly" or row[3] == safe_message:
                return
            cursor.execute(
                "UPDATE dbo.GiaoDichChuyenCoSo SET loi_cuoi = %s, cap_nhat_luc = SYSUTCDATETIME() "
                "WHERE ma_chuyen = %s AND co_so_nguon = %s AND trang_thai = 'dang_xu_ly'",
                [safe_message, transfer_id, source_site],
            )
            _append_event(
                cursor, site_code=source_site, transfer_id=transfer_id,
                student_id=str(row[0]), source_site=source_site, target_site=str(row[1]),
                event="that_bai", actor_id=actor_id, detail=safe_message,
            )
            _audit_transfer(
                cursor, site_code=source_site, actor_id=actor_id,
                action="loi_tam_thoi_chuyen_co_so", transfer_id=transfer_id,
                after={"status": "dang_xu_ly", "retryable": True},
            )


@translate_database_errors
def execute_approved_transfer(*, source_site: str, transfer_id: str, actor_id: str) -> dict[str, Any]:
    source_site = str(source_site).strip().upper()
    snapshot = _transfer_snapshot(source_site, transfer_id)
    state = str(snapshot["status"]).lower()
    step = str(snapshot["step"]).lower()
    if state == "hoan_tat":
        return {"transfer_id": transfer_id, "status": state, "step": step, "complete": True}
    if state != "dang_xu_ly":
        raise AcademicConflict("Chỉ giao dịch đã được Admin Big duyệt mới được thực hiện.")
    _active_destination(str(snapshot["source_site"]), str(snapshot["target_site"]))
    try:
        if step == "da_tiep_nhan":
            _create_destination_profile(snapshot, actor_id)
            _checkpoint_source(snapshot, actor_id, "da_tao_ho_so_dich")
            step = "da_tao_ho_so_dich"
        if step == "da_tao_ho_so_dich":
            _mark_source_student_transferred(snapshot, actor_id)
            step = "da_cap_nhat_nguon"
        if step == "da_cap_nhat_nguon":
            _activate_destination(snapshot, actor_id)
            _checkpoint_source(snapshot, actor_id, "hoan_tat", "hoan_tat")
            step = "hoan_tat"
    except AcademicInfrastructureUnavailable:
        try:
            _record_retryable_transfer_error(source_site, transfer_id, actor_id)
        except AcademicInfrastructureUnavailable:
            pass
        raise
    return {
        "transfer_id": transfer_id, "status": "hoan_tat" if step == "hoan_tat" else "dang_xu_ly",
        "step": step, "complete": step == "hoan_tat",
        "source_site": str(snapshot["source_site"]), "target_site": str(snapshot["target_site"]),
    }


@translate_database_errors
def retry_transfer(*, source_site: str, transfer_id: str, actor_id: str) -> dict[str, Any]:
    source_site = str(source_site).strip().upper()
    alias = require_active_site(source_site)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT trang_thai, buoc_cuoi FROM dbo.GiaoDichChuyenCoSo WITH (UPDLOCK, HOLDLOCK) "
                "WHERE ma_chuyen = %s AND co_so_nguon = %s",
                [transfer_id, source_site],
            )
            row = cursor.fetchone()
            if row is None:
                raise AcademicNotFound
            if str(row[0]).lower() == "hoan_tat":
                return {"transfer_id": transfer_id, "status": "hoan_tat", "step": str(row[1]), "complete": True}
            if str(row[0]).lower() not in {"dang_xu_ly", "that_bai"}:
                raise AcademicConflict("Chỉ giao dịch đã duyệt và chưa hoàn tất mới được retry.")
            if str(row[0]).lower() == "that_bai":
                cursor.execute(
                    "UPDATE dbo.GiaoDichChuyenCoSo SET trang_thai = 'dang_xu_ly', "
                    "cap_nhat_luc = SYSUTCDATETIME(), loi_cuoi = NULL "
                    "WHERE ma_chuyen = %s AND co_so_nguon = %s AND trang_thai = 'that_bai'",
                    [transfer_id, source_site],
                )
            _audit_transfer(
                cursor, site_code=source_site, actor_id=actor_id,
                action="retry_chuyen_co_so", transfer_id=transfer_id,
                before={"status": str(row[0]), "step": str(row[1])},
                after={"status": "dang_xu_ly", "step": str(row[1])},
            )
    return execute_approved_transfer(source_site=source_site, transfer_id=transfer_id, actor_id=actor_id)
