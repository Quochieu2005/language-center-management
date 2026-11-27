"""TC-DTX-01: chuyển cơ sở bằng giao dịch phân tán 2PC (MS DTC) giữa HAI instance SQL Server thật trên cùng một máy.

EVA nằm trên instance mặc định (nguồn), EVB nằm trên instance có tên (đích). Linked Server LS_EVB nối từ EVA sang EVB.
Chỉ dùng database tạm QLTTNN_EVA/QLTTNN_EVB; không đụng QLTTNN_Q1/Q7/TD.

Điều kiện: dịch vụ MS DTC đang chạy; instance thứ hai có tên đặt trong biến môi trường EV_INSTANCE2 (mặc định MSSQLSERVER01
trên máy này). Mọi kết quả ghi vào docs/evidence/TC-DTX-01/<ngày>/results.json.

    python docs/evidence/scripts/ev_dtx.py                 # dựng, chạy kịch bản, ghi kết quả (giữ database để xem)
    python docs/evidence/scripts/ev_dtx.py --cleanup       # xóa database tạm và Linked Server
"""
import datetime
import json
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ev_harness as h  # noqa: E402

import pyodbc  # noqa: E402

# Không dùng connection pooling của ODBC: DROP/OFFLINE database làm các kết nối nằm sẵn trong pool chết âm thầm.
pyodbc.pooling = False

INSTANCE2 = socket.gethostname() + chr(92) + os.environ.get("EV_INSTANCE2", "MSSQLSERVER01")
RUN = os.environ.get("EV_RUN", "2026-11-27")
OUT = os.path.join(h.ROOT, "docs", "evidence", "TC-DTX-01", RUN)
DBA, DBB = "QLTTNN_EVA", "QLTTNN_EVB"
ACTOR = "EVA-TK-000001"

COMMON_BEFORE_30 = ["07_add_auth_session_tables.sql", "08_promote_admin_role_to_admin_big.sql",
                    "09_add_account_slug_and_rename_password_column.sql", "10_add_public_slugs.sql",
                    "12_admin_password_reset_otp.sql", "18_add_notifications.sql", "19_enable_student_accounts.sql",
                    "24_account_status_bit.sql", "26_consolidate_logs_and_remove_notification_reads.sql",
                    "27_move_oauth_identity_to_account.sql", "28_add_tuition_installments.sql",
                    "29_extend_employee_roles.sql"]
AFTER_30 = ["31_add_account_avatar_metadata.sql", "31_add_sepay_tuition_payments.sql",
            "33_add_course_duration_fields.sql", "34_allow_fractional_course_months.sql",
            "35_allow_optional_course_session_count.sql", "36_add_blog_tables.sql",
            "37_merge_consultant_and_placement_roles.sql", "38_add_student_avatar_metadata.sql",
            "39_add_contact_inbox.sql", "40_enable_tuition_refunds.sql",
            "41_merge_receptionist_into_accounting.sql", "42_add_site_staff_notification_audience.sql",
            "43_enforce_contact_site_boundary.sql", "44_revalidate_course_subject_fk.sql",
            "47_add_blog_cover_image.sql", "48_add_nguoi_dung_account_scope.sql", "50_add_transfer_2pc.sql"]


def conn(server, database="master"):
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=%s;DATABASE=%s;Trusted_Connection=yes;Encrypt=yes;"
        "TrustServerCertificate=yes;Connection Timeout=8" % (server, database), autocommit=True)


def main_server():
    return "%s,%s" % (h.HOST, h.PORT)


def run_script(server, database, filename):
    c = conn(server, database).cursor()
    for b in h.batches(os.path.join(h.DB, filename)):
        try:
            c.execute(b)
            while c.nextset():
                pass
        except pyodbc.Error as exc:
            raise RuntimeError("%s (%s): %s" % (filename, database, str(exc)[:240])) from exc


def q(server, database, text, *params):
    c = conn(server, database).cursor()
    c.execute(text, *params)
    try:
        return c.fetchall()
    except pyodbc.ProgrammingError:
        return []


def cleanup():
    for server, db in ((main_server(), DBA), (INSTANCE2, DBB)):
        try:
            q(server, "master", "IF DB_ID('%s') IS NOT NULL BEGIN ALTER DATABASE [%s] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [%s]; END" % (db, db, db))
        except Exception as exc:  # noqa
            print("cleanup", db, type(exc).__name__)
    for server, link in ((main_server(), "LS_EVB"), (INSTANCE2, "LS_EVA")):
        try:
            q(server, "master", "IF EXISTS (SELECT 1 FROM sys.servers WHERE name='%s') EXEC sp_dropserver '%s','droplogins'" % (link, link))
        except Exception as exc:  # noqa
            print("cleanup linked server", link, type(exc).__name__)


def build():
    cleanup()
    for server, db in ((main_server(), DBA), (INSTANCE2, DBB)):
        q(server, "master", "CREATE DATABASE [%s]" % db)
        run_script(server, db, "01_create_schema.sql")
        for f in COMMON_BEFORE_30:
            run_script(server, db, f)
        for code in ("EVA", "EVB"):
            q(server, db, "INSERT dbo.CoSo(ma_co_so, slug, ten_co_so, dia_chi, sdt, trang_thai) VALUES (?,?,?,?,?, 'hoat_dong')",
              code, "co-so-" + code.lower(), "Co so " + code, "Dia chi " + code, "0900000000")
        run_script(server, db, "30_enforce_site_fragment_boundaries.sql")
        for f in AFTER_30:
            run_script(server, db, f)
    q(main_server(), DBA, "SELECT 1")
    m = conn(main_server()).cursor()
    m.execute("EXEC sp_addlinkedserver @server='LS_EVB', @srvproduct='', @provider='MSOLEDBSQL', @datasrc=?, @provstr='TrustServerCertificate=Yes'", INSTANCE2)
    m.execute("EXEC sp_serveroption 'LS_EVB','rpc out','true'")
    m.execute("EXEC sp_serveroption 'LS_EVB','data access','true'")
    m.execute("EXEC sp_addlinkedsrvlogin @rmtsrvname='LS_EVB', @useself='true'")


def fixture():
    for server, db, site in ((main_server(), DBA, "EVA"), (INSTANCE2, DBB, "EVB")):
        pw = "hash-not-a-real-password"
        for acc, uname, role, cs in ((ACTOR, "admin_ev", "admin_big", None), ("EVA-TK-000002", "hv_ev_1", "hoc_vien", "EVA")):
            q(server, db, "INSERT dbo.TaiKhoan(ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban) "
                          "VALUES (?,?,?,?,?,?,?,1,0,1)", acc, uname.replace("_", "-"), uname, uname + "@example.test", pw, role, cs)
        q(server, db, "INSERT dbo.MonHoc(ma_mon, slug, ten_mon, mo_ta) VALUES ('MH-EV','mon-ev',N'Mon kiem chung',N'EV')")
        q(server, db, "INSERT dbo.KhoaHoc(ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, hoc_phi_chuan) "
                      "VALUES ('KH-EV','khoa-ev','MH-EV',N'Khoa kiem chung',N'A1',10,1000000)")
    # Nguồn EVA: 3 học viên (HV1 có tài khoản), 1 giáo viên, 1 phòng, 2 lớp, đăng ký nhất quán với sĩ số
    s, d = main_server(), DBA
    q(s, d, "INSERT dbo.GiaoVien(ma_giao_vien, ma_co_so, ho_ten, chuyen_mon, trang_thai) VALUES ('EVA-GV-000001','EVA','GV EVA','EN','dang_day')")
    q(s, d, "INSERT dbo.PhongHoc(ma_phong, ma_co_so, ten_phong, suc_chua, trang_thai) VALUES ('EVA-PH-000001','EVA','Phong EVA',20,'hoat_dong')")
    students = [("EVA-HV-000001", "hv-eva-1", "Nguyen Van An", "EVA-TK-000002"), ("EVA-HV-000002", "hv-eva-2", "Tran Thi Binh", None),
                ("EVA-HV-000003", "hv-eva-3", "Le Van Cuong", None)]
    for ma, slug, name, acc in students:
        q(s, d, "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ma_tai_khoan, ho_ten, email, ngay_nhap_hoc, trang_thai) "
                "VALUES (?,?, 'EVA','EVA',?,?,?, CONVERT(date, SYSUTCDATETIME()), 'dang_hoc')", ma, slug, acc, name, slug + "@example.test")
    # lớp 1 có HV1 và HV2 (sĩ số 2); lớp 2 có HV1 (sĩ số 1)
    for i, enrolled in ((1, ["EVA-HV-000001", "EVA-HV-000002"]), (2, ["EVA-HV-000001"])):
        q(s, d, "INSERT dbo.LopHoc(ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop, si_so_toi_da, si_so_hien_tai, ngay_khai_giang, "
                "ngay_ket_thuc, lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai) VALUES (?, 'EVA','KH-EV','EVA-GV-000001','EVA-PH-000001',?, 20, ?, "
                "DATEADD(DAY,1,CONVERT(date,SYSUTCDATETIME())), DATEADD(DAY,90,CONVERT(date,SYSUTCDATETIME())), N'T2-T4','18:00','20:00','sap_mo')",
          "EVA-LH-%06d" % i, "Lop EVA %d" % i, len(enrolled))
        for j, hv in enumerate(enrolled, 1):
            q(s, d, "INSERT dbo.DangKy(ma_dang_ky, ma_co_so, ma_hoc_vien, ma_lop, trang_thai) VALUES (?, 'EVA', ?, ?, 'dang_hoc')",
              "EVA-DK-%d%d" % (i, j), hv, "EVA-LH-%06d" % i)


def new_transfer(ma_chuyen, student, source_db_server, source_db, source, target):
    q(source_db_server, source_db,
      "INSERT dbo.GiaoDichChuyenCoSo(ma_chuyen, ma_hoc_vien, co_so_nguon, co_so_dich, trang_thai, buoc_cuoi, ma_tai_khoan_de_nghi, "
      "ma_tai_khoan_quyet_dinh, ly_do_de_nghi, ngay_quyet_dinh) VALUES (?,?,?,?, 'dang_xu_ly','da_tiep_nhan', ?, ?, N'Kiem chung 2PC', SYSUTCDATETIME())",
      ma_chuyen, student, source, target, ACTOR, ACTOR)


def snapshot(student, ma_chuyen):
    """Trạng thái đủ để chứng minh tính nguyên tử ở cả hai site."""
    out = {}
    for label, server, db, site in (("nguon_EVA", main_server(), DBA, "EVA"), ("dich_EVB", INSTANCE2, DBB, "EVB")):
        hv = q(server, db, "SELECT trang_thai, ma_tai_khoan FROM dbo.HocVien WHERE ma_hoc_vien=? AND ma_co_so=?", student, site)
        dk = q(server, db, "SELECT trang_thai, COUNT(*) FROM dbo.DangKy WHERE ma_hoc_vien=? GROUP BY trang_thai", student)
        lop = q(server, db, "SELECT ma_lop, si_so_hien_tai FROM dbo.LopHoc ORDER BY ma_lop")
        ev = q(server, db, "SELECT su_kien FROM dbo.LichSuChuyenCoSo WHERE ma_chuyen=? AND site_ghi=? ORDER BY ma_su_kien", ma_chuyen, site)
        tb = q(server, db, "SELECT COUNT(*) FROM dbo.ThongBao WHERE event_key=?", "transfer-received:" + ma_chuyen)
        giao = q(server, db, "SELECT trang_thai, buoc_cuoi FROM dbo.GiaoDichChuyenCoSo WHERE ma_chuyen=?", ma_chuyen)
        out[label] = {"hoc_vien": [list(r) for r in hv], "dang_ky": [[r[0], r[1]] for r in dk], "si_so_lop": [[r[0], r[1]] for r in lop],
                      "su_kien": [r[0] for r in ev], "thong_bao": tb[0][0], "giao_dich": [list(r) for r in giao]}
    return out


def call_2pc(ma_chuyen, slug):
    try:
        rows = q(main_server(), DBA, "SET NOCOUNT ON; EXEC dbo.sp_chuyen_co_so_2pc @ma_chuyen=?, @linked_server='LS_EVB', @db_dich=?, @slug_goc=?, @actor=?",
                 ma_chuyen, DBB, slug, ACTOR)
        return {"ok": True, "result": [list(r) for r in rows]}
    except Exception as exc:  # noqa
        return {"ok": False, "error": str(exc)[:260]}


def set_db_state(server, db, state):
    q(server, "master", "ALTER DATABASE [%s] SET %s%s" % (db, state, " WITH ROLLBACK IMMEDIATE" if state == "OFFLINE" else ""))


def main():
    if "--cleanup" in sys.argv:
        cleanup()
        print("đã xóa database tạm và Linked Server")
        return
    os.makedirs(OUT, exist_ok=True)
    build()
    fixture()
    result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
              "moi_truong": {"nguon": "instance mặc định (SQL Server 2022), database QLTTNN_EVA",
                             "dich": "instance có tên MSSQLSERVER01 (SQL Server 2025), database QLTTNN_EVB",
                             "co_che": "BEGIN DISTRIBUTED TRANSACTION qua Linked Server LS_EVB, MS DTC"}}
    ver = lambda server: q(server, "master", "SELECT CAST(SERVERPROPERTY('ProductVersion') AS VARCHAR(30))")[0][0]
    result["moi_truong"]["phien_ban"] = {"nguon": ver(main_server()), "dich": ver(INSTANCE2)}

    # K1: thành công — HV1 (có tài khoản, 2 đăng ký) chuyển EVA -> EVB
    new_transfer("EVA-CC-000001", "EVA-HV-000001", main_server(), DBA, "EVA", "EVB")
    before = snapshot("EVA-HV-000001", "EVA-CC-000001")
    r = call_2pc("EVA-CC-000001", "hv-eva-1")
    result["K1_thanh_cong"] = {"truoc": before, "goi": r, "sau": snapshot("EVA-HV-000001", "EVA-CC-000001")}

    # K2: đích từ chối (đã có hồ sơ khác cùng mã ở đích) — nguồn phải còn nguyên
    new_transfer("EVA-CC-000002", "EVA-HV-000002", main_server(), DBA, "EVA", "EVB")
    q(INSTANCE2, DBB, "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai) "
                      "VALUES ('EVA-HV-000002','xung-dot','EVB','EVB',N'Hồ sơ khác', CONVERT(date,SYSUTCDATETIME()), 'dang_hoc')")
    before = snapshot("EVA-HV-000002", "EVA-CC-000002")
    r = call_2pc("EVA-CC-000002", "hv-eva-2")
    after = snapshot("EVA-HV-000002", "EVA-CC-000002")
    result["K2_dich_tu_choi"] = {"truoc": before, "goi": r, "sau": after, "nguon_nguyen_ven": before["nguon_EVA"] == after["nguon_EVA"]}
    q(INSTANCE2, DBB, "DELETE FROM dbo.HocVien WHERE ma_hoc_vien='EVA-HV-000002'")

    # K3: đích OFFLINE — giao dịch hủy, nguồn nguyên vẹn; bật lại rồi chạy lại thì thành công
    before = snapshot("EVA-HV-000002", "EVA-CC-000002")
    set_db_state(INSTANCE2, DBB, "OFFLINE")
    try:
        r_off = call_2pc("EVA-CC-000002", "hv-eva-2")
    finally:
        set_db_state(INSTANCE2, DBB, "ONLINE")
    after_off = snapshot("EVA-HV-000002", "EVA-CC-000002")
    r_on = call_2pc("EVA-CC-000002", "hv-eva-2")
    result["K3_dich_offline_roi_chay_lai"] = {"truoc": before, "goi_khi_offline": r_off, "sau_khi_offline": after_off,
                                              "nguon_nguyen_ven": before["nguon_EVA"] == after_off["nguon_EVA"],
                                              "goi_lai_khi_online": r_on, "cuoi": snapshot("EVA-HV-000002", "EVA-CC-000002")}

    # K4: lỗi Ở NGUỒN SAU KHI đích đã ghi (sĩ số lệch) — hồ sơ đích vừa tạo phải bị hủy theo (điểm khác biệt với đường phục hồi tiến)
    new_transfer("EVA-CC-000003", "EVA-HV-000003", main_server(), DBA, "EVA", "EVB")
    q(main_server(), DBA, "INSERT dbo.DangKy(ma_dang_ky, ma_co_so, ma_hoc_vien, ma_lop, trang_thai) VALUES ('EVA-DK-9', 'EVA', 'EVA-HV-000003', 'EVA-LH-000002', 'dang_hoc')")
    # cố ý KHÔNG tăng si_so_hien_tai của lớp 2 ⇒ nguồn từ chối ở bước đối soát sĩ số, sau khi lời gọi đích đã chạy
    before = snapshot("EVA-HV-000003", "EVA-CC-000003")
    r = call_2pc("EVA-CC-000003", "hv-eva-3")
    after = snapshot("EVA-HV-000003", "EVA-CC-000003")
    result["K4_loi_nguon_sau_khi_dich_ghi"] = {"truoc": before, "goi": r, "sau": after,
                                               "dich_khong_con_ho_so": after["dich_EVB"]["hoc_vien"] == [],
                                               "nguon_nguyen_ven": before["nguon_EVA"] == after["nguon_EVA"]}

    # K5: học viên QUAY LẠI cơ sở cũ (EVB -> EVA) bằng 2PC: hồ sơ cũ da_chuyen_di ở EVA được dùng lại
    m2 = conn(INSTANCE2).cursor()
    m2.execute("EXEC sp_addlinkedserver @server='LS_EVA', @srvproduct='', @provider='MSOLEDBSQL', @datasrc=?, @provstr='TrustServerCertificate=Yes'", socket.gethostname())
    m2.execute("EXEC sp_serveroption 'LS_EVA','rpc out','true'")
    m2.execute("EXEC sp_serveroption 'LS_EVA','data access','true'")
    m2.execute("EXEC sp_addlinkedsrvlogin @rmtsrvname='LS_EVA', @useself='true'")
    new_transfer("EVB-CC-000001", "EVA-HV-000001", INSTANCE2, DBB, "EVB", "EVA")
    try:
        rows = q(INSTANCE2, DBB, "SET NOCOUNT ON; EXEC dbo.sp_chuyen_co_so_2pc @ma_chuyen='EVB-CC-000001', @linked_server='LS_EVA', @db_dich=?, @slug_goc='hv-eva-1', @actor=?", DBA, ACTOR)
        r5 = {"ok": True, "result": [list(r) for r in rows]}
    except Exception as exc:  # noqa
        r5 = {"ok": False, "error": str(exc)[:260]}
    result["K5_quay_lai_co_so_cu"] = {
        "goi": r5,
        "nguon_EVB": [list(r) for r in q(INSTANCE2, DBB, "SELECT trang_thai FROM dbo.HocVien WHERE ma_hoc_vien='EVA-HV-000001'")],
        "dich_EVA": [list(r) for r in q(main_server(), DBA, "SELECT trang_thai, ma_tai_khoan FROM dbo.HocVien WHERE ma_hoc_vien='EVA-HV-000001'")],
        "so_ho_so_o_EVA": q(main_server(), DBA, "SELECT COUNT(*) FROM dbo.HocVien WHERE ma_hoc_vien='EVA-HV-000001'")[0][0],
        "su_kien_EVA": [r[0] for r in q(main_server(), DBA, "SELECT su_kien FROM dbo.LichSuChuyenCoSo WHERE ma_chuyen='EVB-CC-000001' ORDER BY ma_su_kien")],
        "dang_ky_cu_EVA": [[r[0], r[1]] for r in q(main_server(), DBA, "SELECT trang_thai, COUNT(*) FROM dbo.DangKy WHERE ma_hoc_vien='EVA-HV-000001' GROUP BY trang_thai")],
    }

    k1, k3, k4 = result["K1_thanh_cong"], result["K3_dich_offline_roi_chay_lai"], result["K4_loi_nguon_sau_khi_dich_ghi"]
    result["ket_luan"] = {
        "K1": bool(k1["goi"]["ok"] and k1["sau"]["nguon_EVA"]["hoc_vien"][0][0] == "da_chuyen_di"
                   and k1["sau"]["dich_EVB"]["hoc_vien"][0][0] == "dang_hoc" and k1["sau"]["dich_EVB"]["hoc_vien"][0][1] == "EVA-TK-000002"
                   and k1["sau"]["nguon_EVA"]["giao_dich"] == [["hoan_tat", "hoan_tat"]]),
        "K2": bool(not result["K2_dich_tu_choi"]["goi"]["ok"] and result["K2_dich_tu_choi"]["nguon_nguyen_ven"]),
        "K3": bool(not k3["goi_khi_offline"]["ok"] and k3["nguon_nguyen_ven"] and k3["goi_lai_khi_online"]["ok"]),
        "K4": bool(not k4["goi"]["ok"] and k4["dich_khong_con_ho_so"] and k4["nguon_nguyen_ven"]),
        "K5": bool(result["K5_quay_lai_co_so_cu"]["goi"]["ok"] and result["K5_quay_lai_co_so_cu"]["nguon_EVB"] == [["da_chuyen_di"]]
                   and result["K5_quay_lai_co_so_cu"]["dich_EVA"] == [["dang_hoc", "EVA-TK-000002"]]
                   and result["K5_quay_lai_co_so_cu"]["so_ho_so_o_EVA"] == 1
                   and result["K5_quay_lai_co_so_cu"]["dang_ky_cu_EVA"] == [["chuyen_di", 2]]),
    }
    json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    print(json.dumps(result["ket_luan"], ensure_ascii=False))
    for k in ("K1_thanh_cong", "K2_dich_tu_choi", "K3_dich_offline_roi_chay_lai", "K4_loi_nguon_sau_khi_dich_ghi", "K5_quay_lai_co_so_cu"):
        part = result[k]
        g = part.get("goi") or part.get("goi_khi_offline")
        print(k, "goi:", {kk: (str(vv)[:150]) for kk, vv in g.items()})


if __name__ == "__main__":
    main()
