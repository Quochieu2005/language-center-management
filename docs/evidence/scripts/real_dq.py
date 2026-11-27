"""TC-DQ-01 on the REAL topology while some sites are genuinely unreachable (nothing is simulated or changed).

Reads only: per-database counts by SQL, the project's own `student_counts_by_site()`, and the public HTTP endpoints of the
API already running on localhost:8001. Credentials and hosts are never written to the result.
"""
import datetime
import json
import os
import socket
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
API = os.path.join(ROOT, "src", "api")
os.chdir(API)
sys.path.insert(0, API)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django

django.setup()
from django.conf import settings
from django.db import connections

from core.academics.reports import student_counts_by_site
from core.sites.connections import get_site_database_alias

RUN = sys.argv[1] if len(sys.argv) > 1 else "2026-11-27-site-that"
OUT = os.path.join(ROOT, "docs", "evidence", "TC-DQ-01", RUN)
os.makedirs(OUT, exist_ok=True)
SITES = sorted(settings.SITE_DATABASE_ALIASES)
result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
          "note": "Q7 và TD mất kết nối thật tại thời điểm chạy (không mô phỏng); không đổi dữ liệu."}

# 1. which sites answer a TCP connection (reported by site code only)
reach = {}
for site in SITES:
    cfg = connections[get_site_database_alias(site)].settings_dict
    sock = socket.socket()
    sock.settimeout(4)
    try:
        sock.connect((cfg["HOST"], int(cfg.get("PORT") or 1433)))
        reach[site] = "reachable"
    except Exception as exc:  # noqa
        reach[site] = type(exc).__name__
    finally:
        sock.close()
result["tcp_reachability"] = reach
up = [s for s, v in reach.items() if v == "reachable"]
down = [s for s, v in reach.items() if v != "reachable"]

# 2. ground truth: count per reachable database straight from SQL
direct = {}
for site in up:
    with connections[get_site_database_alias(site)].cursor() as cursor:
        cursor.execute("SELECT DB_NAME(), COUNT_BIG(*) FROM dbo.HocVien WHERE ma_co_so = %s AND trang_thai = 'dang_hoc'", [site])
        db, count = cursor.fetchone()
        direct[site] = int(count)
result["direct_sql_active_students"] = direct


def api_call():
    connections.close_all()
    t = time.perf_counter()
    r = student_counts_by_site()
    return r, round(time.perf_counter() - t, 2)


r1, t1 = api_call()
result["global_query_first_call"] = {
    "seconds": t1, "complete": r1["complete"], "missing_sites": r1["missing_sites"],
    "total_active_students": r1["total_active_students"],
    "per_site": {x["site_code"]: x["active_students"] for x in r1["results"]},
}
r2, t2 = api_call()
result["global_query_second_call"] = {"seconds": t2, "complete": r2["complete"], "missing_sites": r2["missing_sites"],
                                      "total_active_students": r2["total_active_students"],
                                      "note": "Gọi lại ngay: site vừa mất kết nối được bỏ qua tức thì (SITE_UNREACHABLE_COOLDOWN_SECONDS)."}
local = {}
for site in up:
    connections.close_all()
    lr = student_counts_by_site(requested_site=site)
    local[site] = {"complete": lr["complete"], "total_active_students": lr["total_active_students"]}
result["local_query_on_reachable_sites"] = local

# 3. the same fact seen over HTTP through the API that is already running (public, no login)
http = {}
for name, path in (("courses", "/api/v1/courses/"), ("blog_articles", "/api/v1/blog/articles/")):
    t = time.perf_counter()
    try:
        with urllib.request.urlopen("http://localhost:8001" + path, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            http[name] = {"status": resp.status, "seconds": round(time.perf_counter() - t, 2), "complete": body.get("complete"),
                          "missing_sites": body.get("missing_sites"), "inconsistent_sites": body.get("inconsistent_sites"),
                          "count": body.get("count")}
    except Exception as exc:  # noqa
        http[name] = {"error": type(exc).__name__ + ": " + str(exc)[:100]}
result["http_public_endpoints"] = http

fc = result["global_query_first_call"]
result["verdict"] = bool(
    down and up
    and fc["complete"] is False and sorted(fc["missing_sites"]) == sorted(down)
    and set(fc["per_site"]) == set(up) and all(fc["per_site"][s] == direct[s] for s in up)
    and fc["total_active_students"] == sum(direct.values())
    and all(v["complete"] and v["total_active_students"] == direct[s] for s, v in local.items())
    and not result["global_query_second_call"]["complete"])
json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=1))
