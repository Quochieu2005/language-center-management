"""Fixture for the scratch sites EVA/EVB: shared catalog + site-local classes, students, enrollments."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ev_harness as h

# classes per site and enrollments per class: deterministic so the expected set is known up front
PLAN = {"EVA": {"classes": 3, "students": 5}, "EVB": {"classes": 2, "students": 4}}


def ident(site, kind, n):
    return "%s-%s-%06d" % (site, kind, n)


def expected_sets():
    out = {}
    for site, p in PLAN.items():
        out[site] = {
            "classes": [ident(site, "LH", i) for i in range(1, p["classes"] + 1)],
            "students": [ident(site, "HV", i) for i in range(1, p["students"] + 1)],
        }
    return out


def build():
    for site, name in h.SITES.items():
        conn = h.connect(name)
        cur = conn.cursor()
        # shared catalog (replicated, same at every site)
        cur.execute("INSERT dbo.MonHoc(ma_mon, slug, ten_mon, mo_ta) VALUES ('MH-EV','mon-ev',N'Mon kiem chung',N'EV')")
        cur.execute(
            "INSERT dbo.KhoaHoc(ma_khoa_hoc, slug, ma_mon, ten_khoa_hoc, trinh_do, so_buoi, hoc_phi_chuan) "
            "VALUES ('KH-EV','khoa-ev','MH-EV',N'Khoa kiem chung',N'A1',10,1000000)")
        p = PLAN[site]
        cur.execute("INSERT dbo.GiaoVien(ma_giao_vien, ma_co_so, ho_ten, chuyen_mon, trang_thai) VALUES (?,?,?,?, 'dang_day')",
                    ident(site, "GV", 1), site, "GV " + site, "EN")
        cur.execute("INSERT dbo.PhongHoc(ma_phong, ma_co_so, ten_phong, suc_chua, trang_thai) VALUES (?,?,?,20,'hoat_dong')",
                    ident(site, "PH", 1), site, "Phong " + site)
        for i in range(1, p["students"] + 1):
            cur.execute(
                "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai) "
                "VALUES (?,?,?,?,?, CONVERT(date, SYSUTCDATETIME()), 'dang_hoc')",
                ident(site, "HV", i), "hv-%s-%d" % (site.lower(), i), site, site, "HV %s %d" % (site, i))
        for i in range(1, p["classes"] + 1):
            # capacity 20, enrolled count kept consistent with DangKy rows below
            enrolled = [j for j in range(1, p["students"] + 1) if j % p["classes"] == i % p["classes"]]
            cur.execute(
                "INSERT dbo.LopHoc(ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop, si_so_toi_da, si_so_hien_tai, "
                "ngay_khai_giang, ngay_ket_thuc, lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai) "
                "VALUES (?,?, 'KH-EV', ?, ?, ?, 20, ?, DATEADD(DAY,1,CONVERT(date,SYSUTCDATETIME())), "
                "DATEADD(DAY,90,CONVERT(date,SYSUTCDATETIME())), N'T2-T4', '18:00', '20:00', 'sap_mo')",
                ident(site, "LH", i), site, ident(site, "GV", 1), ident(site, "PH", 1), "Lop %s %d" % (site, i), len(enrolled))
            for j in enrolled:
                cur.execute(
                    "INSERT dbo.DangKy(ma_dang_ky, ma_co_so, ma_hoc_vien, ma_lop, trang_thai) VALUES (?,?,?,?, 'dang_hoc')",
                    "%s-DK-%d%d" % (site, i, j), site, ident(site, "HV", j), ident(site, "LH", i))
        conn.close()


if __name__ == "__main__":
    build()
    print("fixture ok", expected_sets())
