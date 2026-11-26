import json, os, sys, threading, time, datetime
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import ev_harness as h

API = h.API
os.chdir(API)
sys.path.insert(0, API)
os.environ["SITE_DATABASES_JSON"] = h.scratch_sites_json()
os.environ["AUTH_SESSION_SITE_CODE"] = "EVA"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django
django.setup()
from django.db import connections
from django.db.backends import utils as dbutils
from core.classes.services import register_student_to_class

OUT = os.path.join(h.ROOT, "docs", "evidence", "TC-CON-01", "2026-11-26")
os.makedirs(OUT, exist_ok=True)
SITE = "EVA"
sql = h.connect(h.SITES[SITE])
cur = sql.cursor()


def new_class(code, capacity):
    cur.execute(
        "INSERT dbo.LopHoc(ma_lop, ma_co_so, ma_khoa_hoc, ma_giao_vien, ma_phong, ten_lop, si_so_toi_da, si_so_hien_tai, "
        "ngay_khai_giang, ngay_ket_thuc, lich_hoc, gio_bat_dau, gio_ket_thuc, trang_thai) "
        "VALUES (?,?, 'KH-EV','EVA-GV-000001','EVA-PH-000001',?,?,0, DATEADD(DAY,1,CONVERT(date,SYSUTCDATETIME())), "
        "DATEADD(DAY,90,CONVERT(date,SYSUTCDATETIME())), N'T2-T4', '18:00', '20:00', 'sap_mo')",
        code, SITE, "Lop " + code, capacity)


def new_students(n, start):
    ids = []
    for i in range(start, start + n):
        sid = "EVA-HV-%06d" % i
        cur.execute(
            "INSERT dbo.HocVien(ma_hoc_vien, slug, ma_co_so, co_so_goc, ho_ten, ngay_nhap_hoc, trang_thai) "
            "VALUES (?,?,?,?,?, CONVERT(date, SYSUTCDATETIME()), 'dang_hoc')",
            sid, "hv-con-%d" % i, SITE, SITE, "HV con %d" % i)
        ids.append(sid)
    return ids


def state(class_id):
    cur.execute("SELECT si_so_toi_da, si_so_hien_tai FROM dbo.LopHoc WHERE ma_lop=?", class_id)
    cap, stored = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM dbo.DangKy WHERE ma_lop=? AND trang_thai IN ('da_dang_ky','dang_hoc')", class_id)
    enr = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dbo.HocPhi hp JOIN dbo.DangKy d ON d.ma_dang_ky=hp.ma_dang_ky AND d.ma_co_so=hp.ma_co_so WHERE d.ma_lop=?", class_id)
    fees = cur.fetchone()[0]
    return {"capacity": cap, "stored_count": stored, "enrollments": enr, "tuition_rows": fees,
            "consistent": stored == enr == fees or (stored == enr and fees == enr)}


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


result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
          "note": "Hai database tạm QLTTNN_EVA/EVB trên cùng một instance; gọi trực tiếp register_student_to_class của source."}

# --- A. overlap proof: T1 holds the class lock for 2s after updating the seat count
orig = dbutils.CursorWrapper.execute
holder = {"name": "T1", "marker": "UPDATE dbo.LopHoc SET si_so_hien_tai", "slept": 0.0}


def slow_execute(self, query, params=None):
    out = orig(self, query, params)
    if threading.current_thread().name == holder["name"] and isinstance(query, str) and holder["marker"] in query:
        time.sleep(2.0)
        holder["slept"] += 2.0
    return out


new_class("EVA-LH-C00", 1)
s_a = new_students(2, 100)
dbutils.CursorWrapper.execute = slow_execute
t0 = time.perf_counter()
r1, r2 = {}, {}
th1 = threading.Thread(target=call, args=(s_a[0], "EVA-LH-C00", r1), name="T1")
th2 = threading.Thread(target=call, args=(s_a[1], "EVA-LH-C00", r2), name="T2")
th1.start(); time.sleep(0.5); th2.start(); th1.join(); th2.join()
dbutils.CursorWrapper.execute = orig
result["A_overlap"] = {
    "class": "EVA-LH-C00", "capacity": 1,
    "t1": {"outcome": r1["outcome"], "seconds": round(r1["end"] - r1["start"], 2), "started_at": round(r1["start"] - t0, 2)},
    "t2": {"outcome": r2["outcome"], "seconds": round(r2["end"] - r2["start"], 2), "started_at": round(r2["start"] - t0, 2),
           "error": r2.get("error"), "message": r2.get("message")},
    "t2_waited_for_t1": (r2["end"] - r2["start"]) >= 1.4,
    "final_state": state("EVA-LH-C00"),
}

# --- B. 20 rounds, two sessions released together, capacity 1 (last seat)
rounds = []
next_hv = 200
for n in range(1, 21):
    code = "EVA-LH-C%02d" % (n + 10)
    new_class(code, 1)
    ss = new_students(2, next_hv); next_hv += 2
    bar = threading.Barrier(2)
    recs = [{}, {}]

    def worker(i):
        bar.wait()
        call(ss[i], code, recs[i])

    ths = [threading.Thread(target=worker, args=(i,), name="B%d" % i) for i in range(2)]
    [t.start() for t in ths]; [t.join() for t in ths]
    st = state(code)
    rounds.append({"class": code, "outcomes": sorted(r["outcome"] for r in recs), "state": st,
                   "errors": sorted({r.get("error") for r in recs if r.get("error")})})
result["B_rounds"] = {
    "rounds": len(rounds),
    "exactly_one_success_each_round": all(r["outcomes"] == ["rejected", "success"] for r in rounds),
    "no_overbooking": all(r["state"]["stored_count"] <= r["state"]["capacity"] for r in rounds),
    "counts_consistent": all(r["state"]["stored_count"] == r["state"]["enrollments"] for r in rounds),
    "detail": rounds,
}

# --- C. capacity 5, 12 sessions at once
new_class("EVA-LH-C90", 5)
cs = new_students(12, 400)
bar = threading.Barrier(12)
recs = [dict() for _ in range(12)]


def worker_c(i):
    bar.wait()
    call(cs[i], "EVA-LH-C90", recs[i])


ths = [threading.Thread(target=worker_c, args=(i,), name="C%d" % i) for i in range(12)]
[t.start() for t in ths]; [t.join() for t in ths]
result["C_many"] = {
    "class": "EVA-LH-C90", "capacity": 5, "sessions": 12,
    "successes": sum(1 for r in recs if r["outcome"] == "success"),
    "rejections": sum(1 for r in recs if r["outcome"] == "rejected"),
    "final_state": state("EVA-LH-C90"),
}

result["verdict"] = bool(
    result["A_overlap"]["t1"]["outcome"] == "success" and result["A_overlap"]["t2"]["outcome"] == "rejected"
    and result["A_overlap"]["t2_waited_for_t1"] and result["B_rounds"]["exactly_one_success_each_round"]
    and result["B_rounds"]["no_overbooking"] and result["B_rounds"]["counts_consistent"]
    and result["C_many"]["successes"] == 5 and result["C_many"]["final_state"]["stored_count"] == 5)
json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != "B_rounds"}, ensure_ascii=False, indent=1))
print("B:", {k: v for k, v in result["B_rounds"].items() if k != "detail"})
