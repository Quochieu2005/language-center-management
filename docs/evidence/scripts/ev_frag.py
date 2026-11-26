import json, os, re, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ev_harness as h
import ev_fixture as fx

OUT = os.path.join(h.ROOT, "docs", "evidence", "TC-FRAG-01", "2026-11-26")
os.makedirs(OUT, exist_ok=True)
expected = fx.expected_sets()
result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "sites": {}, "negative_tests": []}

per_site_classes = {}
per_site_enrollments = {}
for site, dbname in h.SITES.items():
    c = h.connect(dbname).cursor()
    info = {}
    c.execute("SELECT @@SERVERNAME, DB_NAME()")
    r = c.fetchone(); info["instance"], info["database"] = r[0], r[1]
    c.execute("SELECT COUNT(*), SUM(CASE WHEN is_disabled=0 AND is_not_trusted=0 THEN 1 ELSE 0 END) "
              "FROM sys.check_constraints WHERE name LIKE N'CK[_]%[_]site[_]local'")
    r = c.fetchone(); info["site_local_checks"] = {"total": r[0], "enabled_and_trusted": r[1]}
    c.execute("SELECT ma_lop, ma_co_so FROM dbo.LopHoc ORDER BY ma_lop")
    classes = [(a, b) for a, b in c.fetchall()]
    per_site_classes[site] = [a for a, _ in classes]
    info["classes"] = per_site_classes[site]
    info["classes_with_wrong_site"] = sum(1 for _, b in classes if b != site)
    c.execute("SELECT ma_dang_ky, ma_co_so, ma_lop, ma_hoc_vien FROM dbo.DangKy ORDER BY ma_dang_ky")
    enr = c.fetchall()
    per_site_enrollments[site] = [e[0] for e in enr]
    info["enrollments"] = len(enr)
    info["enrollments_with_wrong_site"] = sum(1 for e in enr if e[1] != site)
    c.execute("SELECT COUNT(*) FROM dbo.DangKy d LEFT JOIN dbo.LopHoc l ON l.ma_lop=d.ma_lop AND l.ma_co_so=d.ma_co_so WHERE l.ma_lop IS NULL")
    info["enrollments_without_parent_class_in_same_site"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM dbo.DangKy d LEFT JOIN dbo.HocVien h ON h.ma_hoc_vien=d.ma_hoc_vien AND h.ma_co_so=d.ma_co_so WHERE h.ma_hoc_vien IS NULL")
    info["enrollments_without_student_in_same_site"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM dbo.HocVien WHERE ma_co_so <> ?", site)
    info["students_with_wrong_site"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM dbo.LopHoc l WHERE l.si_so_hien_tai <> (SELECT COUNT(*) FROM dbo.DangKy d WHERE d.ma_lop=l.ma_lop AND d.ma_co_so=l.ma_co_so AND d.trang_thai IN ('da_dang_ky','dang_hoc'))")
    info["classes_with_inconsistent_count"] = c.fetchone()[0]
    result["sites"][site] = info

# completeness / reconstruction / disjointness on the class fragment, in the test tool (no central DB, no cross-DB JOIN)
exp_all = sorted(sum((v["classes"] for v in expected.values()), []))
got_all = sorted(sum(per_site_classes.values(), []))
sets = [set(v) for v in per_site_classes.values()]
result["classes"] = {
    "expected": exp_all, "reconstructed": got_all,
    "complete_and_exact": exp_all == got_all,
    "pairwise_disjoint": all(a.isdisjoint(b) for i, a in enumerate(sets) for b in sets[i + 1:]),
    "fragment_sizes": {k: len(v) for k, v in per_site_classes.items()},
}
exp_enr = sum(1 for _ in range(0))
result["enrollments"] = {k: len(v) for k, v in per_site_enrollments.items()}

# shared catalog is replicated, not fragmented: same rows at every site
cat = {}
for site, dbname in h.SITES.items():
    c = h.connect(dbname).cursor()
    c.execute("SELECT ma_mon FROM dbo.MonHoc ORDER BY ma_mon"); m = [r[0] for r in c.fetchall()]
    c.execute("SELECT ma_khoa_hoc FROM dbo.KhoaHoc ORDER BY ma_khoa_hoc"); k = [r[0] for r in c.fetchall()]
    cat[site] = {"MonHoc": m, "KhoaHoc": k}
result["shared_catalog_identical"] = len({json.dumps(v, sort_keys=True) for v in cat.values()}) == 1


def attempt(site, label, sql, params):
    conn = h.connect(h.SITES[site], autocommit=False)
    cur = conn.cursor()
    entry = {"site_database": h.SITES[site], "case": label}
    try:
        cur.execute(sql, params)
        entry["rejected"] = False
        entry["detail"] = "inserted (UNEXPECTED)"
    except Exception as exc:
        msg = str(exc)
        entry["rejected"] = True
        m = re.search(r"(CK_\w+|FK_\w+|PK_\w+|UQ_\w+)", msg)
        entry["constraint"] = m.group(1) if m else None
        entry["sqlstate_error"] = re.search(r"\((\d{3,5})\)", msg).group(1) if re.search(r"\((\d{3,5})\)", msg) else None
    finally:
        conn.rollback()
        conn.close()
    result["negative_tests"].append(entry)


attempt("EVB", "Lớp ghi nhầm ma_co_so=EVA vào DB của EVB",
        "INSERT dbo.LopHoc(ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop, si_so_toi_da, si_so_hien_tai, ngay_khai_giang, ngay_ket_thuc, lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai) "
        "VALUES ('EVA-LH-999999','EVA','KH-EV','EVB-GV-000001','EVB-PH-000001','x',20,0,SYSUTCDATETIME(),DATEADD(DAY,5,SYSUTCDATETIME()),'T2','18:00','20:00','sap_mo')", [])
attempt("EVB", "Học viên ma_co_so=EVA trong DB của EVB",
        "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai) VALUES ('EVA-HV-999999','x-wrong','EVA','EVA','x',SYSUTCDATETIME(),'dang_hoc')", [])
attempt("EVB", "Đăng ký ở EVB trỏ vào lớp thuộc EVA (cha khác site)",
        "INSERT dbo.DangKy(ma_dang_ky, ma_co_so, ma_hoc_vien, ma_lop, trang_thai) VALUES ('EVB-DK-999999','EVB','EVB-HV-000001','EVA-LH-000001','da_dang_ky')", [])
attempt("EVA", "Đăng ký ma_co_so=EVB trong DB của EVA",
        "INSERT dbo.DangKy(ma_dang_ky, ma_co_so, ma_hoc_vien, ma_lop, trang_thai) VALUES ('EVB-DK-999998','EVB','EVA-HV-000002','EVA-LH-000001','da_dang_ky')", [])
result["negative_all_rejected"] = all(e["rejected"] for e in result["negative_tests"])

result["verdict"] = bool(
    result["classes"]["complete_and_exact"] and result["classes"]["pairwise_disjoint"]
    and all(s["classes_with_wrong_site"] == 0 and s["enrollments_with_wrong_site"] == 0 and s["students_with_wrong_site"] == 0
            and s["enrollments_without_parent_class_in_same_site"] == 0 and s["enrollments_without_student_in_same_site"] == 0
            and s["classes_with_inconsistent_count"] == 0 and s["site_local_checks"]["total"] == s["site_local_checks"]["enabled_and_trusted"]
            for s in result["sites"].values())
    and result["negative_all_rejected"] and result["shared_catalog_identical"])
json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=1)[:3500])
