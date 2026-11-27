"""Seed (or remove) a small, clearly tagged data set at every site for the course evidence runs.

Why: TC-FRAG-01, TC-CON-01, TC-DQ-01 and TC-DTX-01 need real classes, students and enrollments at each site, and the
real sites hold almost none. Every row created here has ``LAB`` in its identifier (``Q1-HV-LAB01``) so it can be told
apart from real data and removed again.

Safety: without ``--apply`` nothing is written; the command only prints what it would do. The shared catalog
(``MonHoc``/``KhoaHoc``) is never written here because it is replicated (a direct write at a Subscriber would fight the
Publication): the command uses an existing course that every target site already has. Enrollments go through the real
``register_student_to_class`` service, so tuition rows and installments are created exactly as in production.
"""

import json
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections

from core.classes.services import register_student_to_class
from core.sites.connections import get_site_database_alias

STUDENTS = 8
CLASSES = (("LAB01", 20, "Lớp LAB 01"), ("LAB02", 20, "Lớp LAB 02"), ("LAB03", 1, "Lớp LAB chỗ cuối"))
# (student number, class tag): enrolled through the real service; the other students stay free for TC-CON / TC-DTX.
ENROLLMENTS = ((1, "LAB01"), (2, "LAB01"), (3, "LAB01"), (4, "LAB02"), (5, "LAB02"))
# Delete order: children before parents. Every statement is restricted to rows tagged ``LAB`` at this site.
REMOVE_STEPS = (
    ("PhieuThu", "ma_hoc_phi IN (SELECT hp.ma_hoc_phi FROM dbo.HocPhi hp JOIN dbo.DangKy d ON d.ma_dang_ky = hp.ma_dang_ky AND d.ma_co_so = hp.ma_co_so WHERE d.ma_lop LIKE %s)"),
    ("DotHocPhi", "ma_hoc_phi IN (SELECT hp.ma_hoc_phi FROM dbo.HocPhi hp JOIN dbo.DangKy d ON d.ma_dang_ky = hp.ma_dang_ky AND d.ma_co_so = hp.ma_co_so WHERE d.ma_lop LIKE %s)"),
    ("HocPhi", "ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_lop LIKE %s)"),
    ("Diem", "ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_lop LIKE %s)"),
    ("DiemDanh", "ma_dang_ky IN (SELECT ma_dang_ky FROM dbo.DangKy WHERE ma_lop LIKE %s)"),
    ("DangKy", "ma_lop LIKE %s"),
    ("BuoiHoc", "ma_lop LIKE %s"),
    ("LopHoc", "ma_lop LIKE %s"),
)


def lab_id(site: str, kind: str, tag: str) -> str:
    return f"{site}-{kind}-{tag}"


def class_pattern(site: str) -> str:
    return f"{site}-LH-LAB%"


def student_id(site: str, number: int) -> str:
    return lab_id(site, "HV", f"LAB{number:02d}")


def plan_for(site: str) -> dict:
    return {
        "teacher": lab_id(site, "GV", "LAB01"), "room": lab_id(site, "PH", "LAB01"),
        "students": [student_id(site, n) for n in range(1, STUDENTS + 1)],
        "classes": [lab_id(site, "LH", tag) for tag, _cap, _name in CLASSES],
        "enrollments": [(student_id(site, n), lab_id(site, "LH", tag)) for n, tag in ENROLLMENTS],
    }


class Command(BaseCommand):
    help = "Seed or remove tagged LAB data at each site for the course evidence runs (prints a plan unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--sites", help="Comma separated site codes (default: every configured site).")
        parser.add_argument("--course", help="KhoaHoc code every target site already has (default: the first common one).")
        parser.add_argument("--remove", action="store_true", help="Remove the LAB data instead of creating it.")
        parser.add_argument("--apply", action="store_true", help="Actually write. Without it the command only prints the plan.")

    def handle(self, *args, **options):
        configured = sorted(settings.SITE_DATABASE_ALIASES)
        sites = [s.strip().upper() for s in (options["sites"] or ",".join(configured)).split(",") if s.strip()]
        unknown = [s for s in sites if s not in configured]
        if unknown:
            raise CommandError(f"Unknown site(s): {', '.join(unknown)}. Configured: {', '.join(configured)}.")
        reachable, offline = [], []
        for site in sites:
            try:
                with connections[get_site_database_alias(site)].cursor() as cursor:
                    cursor.execute("SELECT 1")
                reachable.append(site)
            except DatabaseError:
                offline.append(site)
        if offline:
            self.stdout.write(self.style.WARNING(f"Skipping unreachable site(s): {', '.join(offline)}."))
        if not reachable:
            raise CommandError("No target site is reachable.")
        if options["remove"]:
            return self.remove(reachable, options["apply"])
        course = self.pick_course(reachable, options["course"])
        summary = {}
        for site in reachable:
            summary[site] = self.seed(site, course, options["apply"])
        self.stdout.write(json.dumps({"course": course, "applied": options["apply"], "sites": summary}, ensure_ascii=False, indent=2))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing was written. Re-run with --apply to create the data."))

    def pick_course(self, sites, wanted):
        per_site = []
        for site in sites:
            with connections[get_site_database_alias(site)].cursor() as cursor:
                cursor.execute("SELECT ma_khoa_hoc FROM dbo.KhoaHoc")
                per_site.append({str(row[0]) for row in cursor.fetchall()})
        common = set.intersection(*per_site) if per_site else set()
        if wanted:
            if wanted not in common:
                raise CommandError(f"Course {wanted} is not present at every target site ({', '.join(sites)}).")
            return wanted
        if not common:
            raise CommandError(
                "No KhoaHoc exists at every target site. Create one through the admin page first so it replicates "
                "(this command does not write the replicated catalog)."
            )
        return sorted(common)[0]

    def seed(self, site, course, apply):
        plan = plan_for(site)
        alias = get_site_database_alias(site)
        result = {"plan": plan, "created": {"students": 0, "classes": 0, "enrollments": 0}, "skipped_existing": []}
        if not apply:
            return result
        today = date.today()
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT 1 FROM dbo.CoSo WHERE ma_co_so = %s AND trang_thai = 'hoat_dong'", [site])
            if cursor.fetchone() is None:
                raise CommandError(f"Site {site} is not an active CoSo at its own database.")
            cursor.execute("SELECT COUNT(*) FROM dbo.HocVien WHERE ma_hoc_vien LIKE %s", [f"{site}-HV-LAB%"])
            if cursor.fetchone()[0]:
                result["skipped_existing"].append("LAB data already present; nothing created (use --remove first to reseed).")
                return result
            cursor.execute(
                "INSERT dbo.GiaoVien(ma_giao_vien, ma_co_so, ho_ten, chuyen_mon, trang_thai) VALUES (%s, %s, %s, N'LAB', 'dang_day')",
                [plan["teacher"], site, f"Giáo viên LAB {site}"],
            )
            cursor.execute(
                "INSERT dbo.PhongHoc(ma_phong, ma_co_so, ten_phong, suc_chua, trang_thai) VALUES (%s, %s, %s, 30, 'hoat_dong')",
                [plan["room"], site, f"Phòng LAB {site}"],
            )
            for number, sid in enumerate(plan["students"], start=1):
                cursor.execute(
                    "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 'dang_hoc')",
                    [sid, f"lab-{site.lower()}-hv-{number:02d}", site, site, f"Học viên LAB {site} {number:02d}", today],
                )
            result["created"]["students"] = len(plan["students"])
            for (tag, capacity, name), class_id in zip(CLASSES, plan["classes"]):
                cursor.execute(
                    "INSERT dbo.LopHoc(ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop, si_so_toi_da, si_so_hien_tai, "
                    "ngay_khai_giang, ngay_ket_thuc, lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, N'T2-T4', '18:00', '20:00', 'sap_mo')",
                    [class_id, site, course, plan["teacher"], plan["room"], f"{name} {site}", capacity,
                     today + timedelta(days=1), today + timedelta(days=90)],
                )
            result["created"]["classes"] = len(plan["classes"])
        for sid, class_id in plan["enrollments"]:
            register_student_to_class(site_code=site, student_id=sid, class_id=class_id, actor_id=None, remote_ip="127.0.0.1")
            result["created"]["enrollments"] += 1
        return result

    def remove(self, sites, apply):
        for site in sites:
            alias = get_site_database_alias(site)
            counts = {}
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM dbo.LichSuChuyenCoSo WHERE ma_hoc_vien LIKE %s", [f"{site}-HV-LAB%"])
                if cursor.fetchone()[0]:
                    self.stdout.write(self.style.WARNING(
                        f"{site}: LAB students already have transfer history (append-only). The data is kept; remove it by hand if really needed."))
                    continue
                for table, predicate in REMOVE_STEPS:
                    count_sql = f"SELECT COUNT(*) FROM dbo.{table} WHERE {predicate}"
                    cursor.execute(count_sql, [class_pattern(site)])
                    counts[table] = cursor.fetchone()[0]
                for table, where in (("HocVien", "ma_hoc_vien LIKE %s"), ("PhongHoc", "ma_phong LIKE %s"), ("GiaoVien", "ma_giao_vien LIKE %s")):
                    kind = {"HocVien": "HV", "PhongHoc": "PH", "GiaoVien": "GV"}[table]
                    cursor.execute(f"SELECT COUNT(*) FROM dbo.{table} WHERE {where}", [f"{site}-{kind}-LAB%"])
                    counts[table] = cursor.fetchone()[0]
                if apply:
                    for table, predicate in REMOVE_STEPS:
                        cursor.execute(f"DELETE FROM dbo.{table} WHERE {predicate}", [class_pattern(site)])
                    cursor.execute("DELETE FROM dbo.HocVien WHERE ma_hoc_vien LIKE %s", [f"{site}-HV-LAB%"])
                    cursor.execute("DELETE FROM dbo.PhongHoc WHERE ma_phong LIKE %s", [f"{site}-PH-LAB%"])
                    cursor.execute("DELETE FROM dbo.GiaoVien WHERE ma_giao_vien LIKE %s", [f"{site}-GV-LAB%"])
            verb = "Removed" if apply else "Would remove"
            self.stdout.write(f"{site}: {verb} {json.dumps(counts)}")
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run: nothing was deleted. Re-run with --apply to delete."))
