import json, os, sys, time, datetime
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import ev_harness as h

API = h.API
os.chdir(API)
sys.path.insert(0, API)
os.environ["SITE_DATABASES_JSON"] = h.scratch_sites_json()
os.environ["AUTH_SESSION_SITE_CODE"] = "EVA"
os.environ["SITE_UNREACHABLE_COOLDOWN_SECONDS"] = "2"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django
django.setup()
from django.db import connections
from core.academics.reports import student_counts_by_site

OUT = os.path.join(h.ROOT, "docs", "evidence", "TC-DQ-01", "2026-11-26")
os.makedirs(OUT, exist_ok=True)


def direct():
    out = {}
    for site, name in h.SITES.items():
        c = h.connect(name).cursor()
        c.execute("SELECT COUNT_BIG(*) FROM dbo.HocVien WHERE ma_co_so=? AND trang_thai='dang_hoc'", site)
        out[site] = int(c.fetchone()[0])
    return out


def set_state(db, state):
    conn = h.connect("master")
    conn.cursor().execute("ALTER DATABASE [%s] SET %s WITH ROLLBACK IMMEDIATE" % (db, state))
    conn.close()


def api():
    connections.close_all()
    t = time.perf_counter()
    r = student_counts_by_site()
    return r, round(time.perf_counter() - t, 2)


def brief(r):
    return {"complete": r["complete"], "missing_sites": r["missing_sites"], "total_active_students": r["total_active_students"],
            "per_site": {x["site_code"]: x["active_students"] for x in r["results"]}}


result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
          "note": "Hai database tạm QLTTNN_EVA/EVB cùng instance; EVB được đưa OFFLINE bằng ALTER DATABASE để mô phỏng site mất kết nối."}
expected = direct()
result["expected_by_direct_sql_per_database"] = expected

r1, t1 = api()
result["step1_all_sites_up"] = {**brief(r1), "seconds": t1,
                                "matches_direct": brief(r1)["per_site"] == expected and r1["total_active_students"] == sum(expected.values())}
# 2a. database OFFLINE on a reachable instance: ODBC reports login failure (SQLSTATE 28000 -> django InterfaceError)
offline_case = {"attempts": []}
try:
    set_state(h.SITES["EVB"], "OFFLINE")
    for attempt in range(1, 5):
        entry = {"attempt": attempt}
        try:
            r, secs = api()
            entry.update(returned=True, complete=r["complete"], missing_sites=r["missing_sites"])
        except Exception as exc:
            entry.update(returned=False, exception_type=type(exc).__module__ + "." + type(exc).__name__,
                         is_DatabaseError_subclass=isinstance(exc, django.db.utils.DatabaseError))
        offline_case["attempts"].append(entry)
        time.sleep(2.6)
finally:
    set_state(h.SITES["EVB"], "ONLINE")
offline_case["any_attempt_raised_instead_of_reporting_missing_site"] = any(not e["returned"] for e in offline_case["attempts"])
result["step2a_EVB_database_offline_on_reachable_instance"] = offline_case
time.sleep(2.6)

# 2b. site unreachable on the network (closed port, like a powered-off VM / dropped VPN): OperationalError path
wrapper = connections["site_evb"]
real_port = wrapper.settings_dict["PORT"]
try:
    wrapper.close()
    wrapper.settings_dict["PORT"] = "1"
    r2, t2 = api()
    wrapper.settings_dict["PORT"] = "1"
    local = student_counts_by_site(requested_site="EVA")
    result["step2b_EVB_unreachable"] = {**brief(r2), "seconds": t2,
                                        "EVB_not_reported_as_zero": "EVB" not in brief(r2)["per_site"] and r2["missing_sites"] == ["EVB"],
                                        "partial_total_equals_EVA_only": r2["total_active_students"] == expected["EVA"],
                                        "local_EVA_query_still_works": local["total_active_students"] == expected["EVA"] and local["complete"]}
finally:
    wrapper.settings_dict["PORT"] = real_port
    wrapper.close()
time.sleep(2.6)  # cooldown for fast-skip of the unreachable site (configured to 2 s for this run)
r3, t3 = api()
result["step3_EVB_back_online"] = {**brief(r3), "seconds": t3,
                                   "matches_direct": brief(r3)["per_site"] == expected and r3["complete"]}
result["verdict"] = bool(result["step1_all_sites_up"]["matches_direct"]
                         and result["step2b_EVB_unreachable"]["EVB_not_reported_as_zero"]
                         and result["step2b_EVB_unreachable"]["partial_total_equals_EVA_only"]
                         and result["step2b_EVB_unreachable"]["local_EVA_query_still_works"]
                         and result["step3_EVB_back_online"]["matches_direct"])
json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=1))
