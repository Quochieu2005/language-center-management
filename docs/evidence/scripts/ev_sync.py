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
from core.auth import account_replication as ar
from core.blog import sync_queue
from core.blog.write_services import write_blog

OUT = os.path.join(h.ROOT, "docs", "evidence", "TC-SYNC-01", "2026-11-26")
os.makedirs(OUT, exist_ok=True)
ACTOR = "EVA-TK-000001"
result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
          "note": "Hai database tạm QLTTNN_EVA (authority) và QLTTNN_EVB cùng instance; EVB mất kết nối được mô phỏng bằng cách trỏ cổng kết nối sang cổng đóng, như máy tắt hoặc VPN rớt."}
sql = {s: h.connect(n) for s, n in h.SITES.items()}


def q(site, text, *params):
    c = sql[site].cursor()
    c.execute(text, *params)
    return c


wrapper = connections["site_evb"]
real_port = wrapper.settings_dict["PORT"]


def evb_down():
    wrapper.close()
    wrapper.settings_dict["PORT"] = "1"


def evb_up():
    wrapper.settings_dict["PORT"] = real_port
    wrapper.close()
    time.sleep(2.6)  # cooldown for fast-skip of an unreachable site (2 s in this run)


# ---------------- Part 1: account replication across an outage ----------------
q("EVA", "INSERT dbo.TaiKhoan(ma_tai_khoan, slug, ten_dang_nhap, email, mat_khau, vai_tro, ma_co_so, trang_thai, bat_buoc_doi_mat_khau, phien_ban) "
         "VALUES (?,?,?,?,?, 'admin_big', NULL, 1, 0, 1)",
  ACTOR, "admin-ev", "admin_ev", "admin-ev@example.test", "hash-not-a-real-password")
queued = q("EVA", "SELECT site_dich, so_lan_thu FROM dbo.DongBoTaiKhoan WHERE ma_tai_khoan=?", ACTOR).fetchall()
part1 = {"queue_after_insert_at_authority": [{"site": r[0], "attempts": r[1]} for r in queued],
         "account_missing_at_EVB_before": q("EVB", "SELECT COUNT(*) FROM dbo.TaiKhoan WHERE ma_tai_khoan=?", ACTOR).fetchone()[0] == 0}
try:
    evb_down()
    out1 = ar.sync_accounts()
    row = q("EVA", "SELECT so_lan_thu, loi FROM dbo.DongBoTaiKhoan WHERE ma_tai_khoan=? AND site_dich='EVB'", ACTOR).fetchone()
    part1["worker_pass_while_EVB_down"] = {**out1, "queue_row_kept": row is not None,
                                           "attempts": row[0] if row else None, "error_recorded": row[1] if row else None}
finally:
    evb_up()
q("EVA", "UPDATE dbo.DongBoTaiKhoan SET thu_lai_luc_utc = SYSUTCDATETIME()")  # skip the 10 s backoff for the demo
out2 = ar.sync_accounts()
cols = ar.ACCOUNT_COLUMNS
a = q("EVA", "SELECT %s FROM dbo.TaiKhoan WHERE ma_tai_khoan=?" % ",".join(cols), ACTOR).fetchone()
b = q("EVB", "SELECT %s FROM dbo.TaiKhoan WHERE ma_tai_khoan=?" % ",".join(cols), ACTOR).fetchone()
part1["worker_pass_after_recovery"] = {**out2, "replica_equals_authority": a is not None and b is not None and tuple(a) == tuple(b),
                                       "queue_empty": q("EVA", "SELECT COUNT(*) FROM dbo.DongBoTaiKhoan WHERE ma_tai_khoan=?", ACTOR).fetchone()[0] == 0}
out3 = ar.sync_accounts()
part1["rerun_is_noop"] = out3 == {"delivered": 0, "deferred": 0}
result["part1_account_replication"] = part1

# ---------------- Part 2: Blog writes while EVB is down ----------------
CAT = {"slug": "danh-muc-ev", "name": "Danh muc EV", "description": None, "status": "hoat_dong"}
ART = {"slug": "bai-ev", "category_slug": "danh-muc-ev", "title": "Tieu de goc", "excerpt": "Tom tat", "content": "Noi dung",
       "reading_time_minutes": 3, "status": "da_xuat_ban", "published_at": datetime.datetime(2026, 11, 26, 1, 0, tzinfo=datetime.timezone.utc),
       "cover_public_id": None, "cover_url": None}


def brief(res):
    return {"complete": res["complete"], "site_codes": res.get("site_codes", []),
            "missing_sites": res.get("missing_sites", []), "idempotent_replay": res.get("idempotent_replay")}


part2 = {}
r = write_blog(entity="category", action="tao", slug=CAT["slug"], payload=CAT, idempotency_key="ev-key-cat", actor_id=ACTOR)
part2["step1_create_category_all_up"] = brief(r)
r = write_blog(entity="article", action="tao", slug=ART["slug"], payload=ART, idempotency_key="ev-key-art", actor_id=ACTOR)
part2["step2_create_article_all_up"] = brief(r)

try:
    evb_down()
    r = write_blog(entity="article", action="sua", slug="bai-ev", payload={"title": "Sua lan 1 khi EVB mat ket noi"},
                   idempotency_key="ev-key-edit1", actor_id=ACTOR)
    part2["step3_edit1_while_EVB_down"] = {**brief(r), "queue": sync_queue.status()}
    r = write_blog(entity="article", action="sua", slug="bai-ev", payload={"title": "Sua lan 2 khi EVB mat ket noi"},
                   idempotency_key="ev-key-edit2", actor_id=ACTOR)
    part2["step4_edit2_while_EVB_down"] = {**brief(r), "queue": sync_queue.status()}
    t_a = q("EVA", "SELECT tieu_de, tom_tat, noi_dung, trang_thai, so_phut_doc, ngay_xuat_ban_utc FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()
    t_b = q("EVB", "SELECT tieu_de, tom_tat, noi_dung, trang_thai, so_phut_doc, ngay_xuat_ban_utc FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()
    part2["state_while_down"] = {"EVA": {"title": t_a[0]}, "EVB": {"title": t_b[0]},
                                 "sites_differ_as_expected": tuple(t_a) != tuple(t_b)}
    part2["worker_pass_while_EVB_down"] = sync_queue.reconcile_pending_blog_writes()
finally:
    evb_up()

part2["step5_worker_after_recovery"] = sync_queue.reconcile_pending_blog_writes()
t_a = q("EVA", "SELECT tieu_de, tom_tat, noi_dung, trang_thai, so_phut_doc, ngay_xuat_ban_utc FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()
t_b = q("EVB", "SELECT tieu_de, tom_tat, noi_dung, trang_thai, so_phut_doc, ngay_xuat_ban_utc FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()
part2["converged"] = {"EVA": {"title": t_a[0]}, "EVB": {"title": t_b[0]},
                      "identical": tuple(t_a) == tuple(t_b), "final_title_is_last_edit": t_b[0] == "Sua lan 2 khi EVB mat ket noi"}

# idempotent retry of the LATEST completed edit: must not rewrite either site
ts_a = q("EVA", "SELECT cap_nhat_luc_utc FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()[0]
ts_b = q("EVB", "SELECT cap_nhat_luc_utc FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()[0]
r = write_blog(entity="article", action="sua", slug="bai-ev", payload={"title": "Sua lan 2 khi EVB mat ket noi"},
               idempotency_key="ev-key-edit2", actor_id=ACTOR)
n_a = q("EVA", "SELECT cap_nhat_luc_utc, tieu_de FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()
n_b = q("EVB", "SELECT cap_nhat_luc_utc, tieu_de FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()
part2["retry_latest_key_after_completion"] = {**brief(r), "rows_unchanged": n_a[0] == ts_a and n_b[0] == ts_b,
                                             "title_still_last_edit": n_a[1] == n_b[1] == "Sua lan 2 khi EVB mat ket noi"}
# replaying an OLDER key after a newer edit must not re-apply the stale change at any site
r_old = write_blog(entity="article", action="sua", slug="bai-ev", payload={"title": "Sua lan 1 khi EVB mat ket noi"},
                   idempotency_key="ev-key-edit1", actor_id=ACTOR)
t_after = [q(s_, "SELECT tieu_de FROM dbo.BaiVietBlog WHERE slug='bai-ev'").fetchone()[0] for s_ in ("EVA", "EVB")]
part2["retry_older_key_after_newer_edit"] = {**brief(r_old), "stale_change_not_reapplied": t_after == ["Sua lan 2 khi EVB mat ket noi"] * 2}
part2["queue_after"] = sync_queue.status()
result["part2_blog_queue"] = part2

p1, p2 = result["part1_account_replication"], result["part2_blog_queue"]
result["verdict"] = bool(
    p1["worker_pass_while_EVB_down"]["queue_row_kept"] and p1["worker_pass_after_recovery"]["replica_equals_authority"]
    and p1["worker_pass_after_recovery"]["queue_empty"] and p1["rerun_is_noop"]
    and p2["step3_edit1_while_EVB_down"]["complete"] is False and p2["step4_edit2_while_EVB_down"]["complete"] is False
    and p2["state_while_down"]["sites_differ_as_expected"] and p2["converged"]["identical"]
    and p2["converged"]["final_title_is_last_edit"] and p2["retry_latest_key_after_completion"]["rows_unchanged"] and p2["retry_older_key_after_newer_edit"]["stale_change_not_reapplied"]
    and p2["queue_after"]["pending_count"] == 0)
json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
