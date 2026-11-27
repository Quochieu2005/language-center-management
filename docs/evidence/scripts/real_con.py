"""TC-CON-01 on a REAL site (default Q1): two sessions race for the last seat, using the project's own service.

Needs the LAB data from `manage.py seed_lab_data --sites Q1 --apply` (class LAB03 has one seat, students LAB06 to LAB08
are free). It adds a few more tagged LAB classes and students (all removed again by `seed_lab_data --remove --apply`)
and uses the real settings and connection from src/api/.env. Nothing but LAB rows is written.
"""
import datetime
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
API = os.path.join(ROOT, "src", "api")
os.chdir(API)
sys.path.insert(0, API)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django

django.setup()
from django.db import connections
from django.db.backends import utils as dbutils

from core.classes.services import register_student_to_class
from core.sites.connections import get_site_database_alias

SITE = sys.argv[1].upper() if len(sys.argv) > 1 else "Q1"
RUN = sys.argv[2] if len(sys.argv) > 2 else "2026-11-27-site-that"
OUT = os.path.join(ROOT, "docs", "evidence", "TC-CON-01", RUN)
os.makedirs(OUT, exist_ok=True)
alias = get_site_database_alias(SITE)
cur = connections[alias].cursor()
cur.execute("SELECT 1 FROM dbo.LopHoc WHERE ma_lop = %s", [f"{SITE}-LH-LAB03"])
if cur.fetchone() is None:
    sys.exit("Run `manage.py seed_lab_data --sites %s --apply` first (class %s-LH-LAB03 not found)." % (SITE, SITE))
cur.execute("SELECT ma_khoa_hoc, ma_giao_vien, ma_phong FROM dbo.LopHoc WHERE ma_lop = %s", [f"{SITE}-LH-LAB03"])
COURSE, TEACHER, ROOM = cur.fetchone()
cur.execute("SELECT @@SERVERNAME, DB_NAME()")
SERVER, DBNAME = cur.fetchone()


def new_class(code, capacity):
    cur.execute(
        "INSERT dbo.LopHoc(ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop, si_so_toi_da, si_so_hien_tai, "
        "ngay_khai_giang, ngay_ket_thuc, lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 0, DATEADD(DAY, 1, CONVERT(date, SYSUTCDATETIME())), "
        "DATEADD(DAY, 90, CONVERT(date, SYSUTCDATETIME())), N'T2-T4', '18:00', '20:00', 'sap_mo')",
        [code, SITE, COURSE, TEACHER, ROOM, "Lớp LAB tranh chỗ " + code, capacity])


def extra_students(ids):
    """Create tagged LAB students if missing. A student may hold only ONE active enrollment per course, so every
    contender in every race below is a different student."""
    for sid in ids:
        number = sid.split("LAB", 1)[1]
        cur.execute("SELECT 1 FROM dbo.HocVien WHERE ma_hoc_vien = %s", [sid])
        if cur.fetchone() is None:
            cur.execute(
                "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai) "
                "VALUES (%s, %s, %s, %s, %s, CONVERT(date, SYSUTCDATETIME()), 'dang_hoc')",
                [sid, f"lab-{SITE.lower()}-{number.lower()}", SITE, SITE, f"Học viên LAB {SITE} {number}"])
    return list(ids)


def state(class_id):
    cur.execute("SELECT si_so_toi_da, si_so_hien_tai FROM dbo.LopHoc WHERE ma_lop = %s", [class_id])
    cap, stored = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM dbo.DangKy WHERE ma_lop = %s AND trang_thai IN ('da_dang_ky', 'dang_hoc')", [class_id])
    enrollments = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dbo.HocPhi hp JOIN dbo.DangKy d ON d.ma_dang_ky = hp.ma_dang_ky AND d.ma_co_so = hp.ma_co_so "
                "WHERE d.ma_lop = %s", [class_id])
    fees = cur.fetchone()[0]
    return {"capacity": cap, "stored_count": stored, "enrollments": enrollments, "tuition_rows": fees,
            "consistent": stored == enrollments == fees}


def call(student, class_id, rec):
    rec["start"] = time.perf_counter()
    try:
        res = register_student_to_class(site_code=SITE, student_id=student, class_id=class_id, actor_id=None, remote_ip="127.0.0.1")
        rec["outcome"] = "success"
        rec["remaining_seats"] = res["remaining_seats"]
    except Exception as exc:  # noqa
        rec["outcome"] = "rejected"
        rec["error"] = type(exc).__name__
        rec["message"] = str(exc)[:120]
    finally:
        rec["end"] = time.perf_counter()
        connections.close_all()


result = {
    "run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "environment": {"site": SITE, "instance": SERVER, "database": DBNAME,
                    "note": "Site thật theo cấu hình; gọi trực tiếp register_student_to_class; chỉ ghi dữ liệu mang nhãn LAB."},
}

# --- A. overlap proof on the one-seat LAB class: session 1 holds the class lock for 2 s after taking the seat
orig = dbutils.CursorWrapper.execute
marker = "UPDATE dbo.LopHoc SET si_so_hien_tai"


def slow_execute(self, query, params=None):
    out = orig(self, query, params)
    if threading.current_thread().name == "T1" and isinstance(query, str) and marker in query:
        time.sleep(2.0)
    return out


class_a = f"{SITE}-LH-LAB03"
before_a = state(class_a)
dbutils.CursorWrapper.execute = slow_execute
t0 = time.perf_counter()
r1, r2 = {}, {}
th1 = threading.Thread(target=call, args=(f"{SITE}-HV-LAB06", class_a, r1), name="T1")
th2 = threading.Thread(target=call, args=(f"{SITE}-HV-LAB07", class_a, r2), name="T2")
th1.start(); time.sleep(0.5); th2.start(); th1.join(); th2.join()
dbutils.CursorWrapper.execute = orig
result["A_overlap"] = {
    "class": class_a, "capacity": 1, "state_before": before_a,
    "t1": {"outcome": r1["outcome"], "seconds": round(r1["end"] - r1["start"], 2), "started_at": round(r1["start"] - t0, 2)},
    "t2": {"outcome": r2["outcome"], "seconds": round(r2["end"] - r2["start"], 2), "started_at": round(r2["start"] - t0, 2),
           "error": r2.get("error"), "message": r2.get("message")},
    "t2_waited_for_t1": (r2["end"] - r2["start"]) >= 1.4,
    "final_state": state(class_a),
}

# --- B. 10 rounds, a fresh one-seat class and a fresh pair of students each time, released together
rounds = []
for n in range(1, 11):
    code = f"{SITE}-LH-LABR{n:02d}"
    new_class(code, 1)
    bar = threading.Barrier(2)
    recs = [{}, {}]
    students = extra_students([f"{SITE}-HV-LABB{n:02d}A", f"{SITE}-HV-LABB{n:02d}B"])

    def worker(i, code=code, bar=bar, recs=recs, students=students):
        bar.wait()
        call(students[i], code, recs[i])

    ths = [threading.Thread(target=worker, args=(i,), name=f"B{i}") for i in range(2)]
    [t.start() for t in ths]; [t.join() for t in ths]
    rounds.append({"class": code, "outcomes": sorted(r["outcome"] for r in recs), "state": state(code)})
result["B_rounds"] = {
    "rounds": len(rounds),
    "exactly_one_success_each_round": all(r["outcomes"] == ["rejected", "success"] for r in rounds),
    "no_overbooking": all(r["state"]["stored_count"] <= r["state"]["capacity"] for r in rounds),
    "counts_consistent": all(r["state"]["consistent"] for r in rounds),
    "detail": rounds,
}

# --- C. five seats, twelve sessions at once
new_class(f"{SITE}-LH-LABM01", 5)
ids = extra_students([f"{SITE}-HV-LABX{i:02d}" for i in range(1, 13)])
bar = threading.Barrier(12)
recs = [dict() for _ in range(12)]


def worker_c(i):
    bar.wait()
    call(ids[i], f"{SITE}-LH-LABM01", recs[i])


ths = [threading.Thread(target=worker_c, args=(i,), name=f"C{i}") for i in range(12)]
[t.start() for t in ths]; [t.join() for t in ths]
result["C_many"] = {
    "class": f"{SITE}-LH-LABM01", "capacity": 5, "sessions": 12,
    "successes": sum(1 for r in recs if r["outcome"] == "success"),
    "rejections": sum(1 for r in recs if r["outcome"] == "rejected"),
    "final_state": state(f"{SITE}-LH-LABM01"),
}

result["verdict"] = bool(
    result["A_overlap"]["t1"]["outcome"] == "success" and result["A_overlap"]["t2"]["outcome"] == "rejected"
    and result["A_overlap"]["t2_waited_for_t1"] and result["A_overlap"]["final_state"]["consistent"]
    and result["B_rounds"]["exactly_one_success_each_round"] and result["B_rounds"]["no_overbooking"]
    and result["B_rounds"]["counts_consistent"]
    and result["C_many"]["successes"] == 5 and result["C_many"]["final_state"]["consistent"])
json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != "B_rounds"}, ensure_ascii=False, indent=1))
print("B:", {k: v for k, v in result["B_rounds"].items() if k != "detail"})
