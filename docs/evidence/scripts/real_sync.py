"""TC-SYNC-01 (phần mất kết nối) trên Q1 thật, khi Q7 và TD đang mất kết nối thật.

Tạo một danh mục và một bài Blog NHÁP mang nhãn LAB (không hiển thị công khai), sửa hai lần, ghi lại hàng đợi.
Không dọn: bài và hàng đợi được giữ để chạy phần phục hồi khi Q7 và TD lên (xem docs/QLTTNN-Chay-Bang-Chung-Site-That.md).
Không ghi host hay thông tin đăng nhập.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
API = os.path.join(ROOT, "src", "api")
os.chdir(API)
sys.path.insert(0, API)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django

django.setup()
from django.db import connections

from core.blog import sync_queue
from core.blog.write_services import write_blog
from core.sites.connections import get_site_database_alias

RUN = sys.argv[1] if len(sys.argv) > 1 else "2026-11-27-site-that"
OUT = os.path.join(ROOT, "docs", "evidence", "TC-SYNC-01", RUN)
os.makedirs(OUT, exist_ok=True)
ACTOR = "Q1-TK-000001"
STAMP = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
CAT = {"slug": "lab-ev", "name": "LAB bang chung", "description": None, "status": "hoat_dong"}
ART = {"slug": "lab-bai-ev", "category_slug": "lab-ev", "title": "LAB tieu de goc", "excerpt": "LAB tom tat", "content": "LAB noi dung",
       "reading_time_minutes": 1, "status": "nhap", "published_at": None, "cover_public_id": None, "cover_url": None}


def brief(res):
    return {"complete": res["complete"], "site_codes": res.get("site_codes", []), "missing_sites": res.get("missing_sites", []),
            "idempotent_replay": res.get("idempotent_replay")}


def title_at_q1():
    with connections[get_site_database_alias("Q1")].cursor() as cur:
        cur.execute("SELECT tieu_de, trang_thai FROM dbo.BaiVietBlog WHERE slug = %s", [ART["slug"]])
        row = cur.fetchone()
        return None if row is None else {"title": row[0], "status": row[1]}


result = {"run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
          "note": "Q7 và TD mất kết nối thật tại thời điểm chạy. Bài LAB ở trạng thái nháp, được giữ lại để chạy phần phục hồi."}
result["queue_before"] = sync_queue.status()
steps = {}
r = write_blog(entity="category", action="tao", slug=CAT["slug"], payload=CAT, idempotency_key=f"lab-cat-{STAMP}", actor_id=ACTOR)
steps["1_tao_danh_muc"] = {**brief(r), "queue": sync_queue.status()}
r = write_blog(entity="article", action="tao", slug=ART["slug"], payload=ART, idempotency_key=f"lab-art-{STAMP}", actor_id=ACTOR)
steps["2_tao_bai"] = {**brief(r), "queue": sync_queue.status()}
r = write_blog(entity="article", action="sua", slug=ART["slug"], payload={"title": "LAB sua lan 1 khi Q7 va TD mat ket noi"},
               idempotency_key=f"lab-e1-{STAMP}", actor_id=ACTOR)
steps["3_sua_lan_1"] = {**brief(r), "queue": sync_queue.status()}
r = write_blog(entity="article", action="sua", slug=ART["slug"], payload={"title": "LAB sua lan 2 khi Q7 va TD mat ket noi"},
               idempotency_key=f"lab-e2-{STAMP}", actor_id=ACTOR)
steps["4_sua_lan_2"] = {**brief(r), "queue": sync_queue.status()}
steps["5_q1_hien_tai"] = title_at_q1()
steps["6_worker_khi_van_mat_ket_noi"] = sync_queue.reconcile_pending_blog_writes()
steps["7_queue_sau_worker"] = sync_queue.status()
result["steps"] = steps
result["verdict_outage_part"] = bool(
    steps["4_sua_lan_2"]["missing_sites"] and not steps["4_sua_lan_2"]["complete"]
    and steps["5_q1_hien_tai"] and steps["5_q1_hien_tai"]["title"].endswith("mat ket noi")
    and "lan 2" in steps["5_q1_hien_tai"]["title"])
json.dump(result, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
