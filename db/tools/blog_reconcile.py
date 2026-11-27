"""Bring ONE blog article of a site back to the authority's copy when the copies drifted (dry-run by default).

The application refuses to edit an article whose copies differ between sites, so a drifted copy has to be reconciled
first. This tool copies the content columns (title, excerpt, content, reading time, status, published date, cover) of one
article from the authority site to another site, inside one local transaction, and appends an audit row to that site's
``Logs``. Ids, category and timestamps of the target are not touched. Credentials are never printed.

    src/api/.venv/Scripts/python.exe db/tools/blog_reconcile.py --slug <slug> --to TD            # dry run: show the diff
    src/api/.venv/Scripts/python.exe db/tools/blog_reconcile.py --slug <slug> --to TD --apply    # apply and audit
"""

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
API = os.path.join(ROOT, "src", "api")
os.chdir(API)
sys.path.insert(0, API)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.db import connections, transaction  # noqa: E402

from core.sites.connections import get_site_database_alias  # noqa: E402

COLUMNS = ("tieu_de", "tom_tat", "noi_dung", "so_phut_doc", "trang_thai", "ngay_xuat_ban_utc", "anh_bia_public_id", "anh_bia_url")


def read(site, slug):
    with connections[get_site_database_alias(site)].cursor() as cursor:
        cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM dbo.BaiVietBlog WHERE slug = %s", [slug])
        row = cursor.fetchone()
    return None if row is None else dict(zip(COLUMNS, row))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--to", required=True, help="site code to bring back to the authority copy")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    authority = str(settings.AUTH_SESSION_SITE_CODE).upper()
    target = args.to.upper()
    if target == authority:
        sys.exit("Site đích phải khác authority.")
    source_row, target_row = read(authority, args.slug), read(target, args.slug)
    if source_row is None:
        sys.exit(f"Không có bài {args.slug!r} ở authority {authority}.")
    if target_row is None:
        sys.exit(f"Bài {args.slug!r} chưa có ở {target}; dùng đường ghi Blog của ứng dụng để tạo, không dùng tool này.")
    diff = {c: (len(str(target_row[c] or "")), len(str(source_row[c] or ""))) for c in COLUMNS if target_row[c] != source_row[c]}
    print(f"Authority {authority} → {target}, bài {args.slug}: cột khác (độ dài ở {target}, độ dài ở {authority}):", diff or "không có")
    if not diff:
        return
    if not args.apply:
        print("Dry run: chưa đổi gì. Thêm --apply để chép bản của authority sang", target)
        return
    alias = get_site_database_alias(target)
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(
                f"UPDATE dbo.BaiVietBlog SET {', '.join(c + ' = %s' for c in COLUMNS)}, cap_nhat_luc_utc = SYSUTCDATETIME() WHERE slug = %s",
                [*[source_row[c] for c in COLUMNS], args.slug],
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Không cập nhật đúng một dòng; đã hủy.")
            cursor.execute("SELECT NEXT VALUE FOR dbo.Seq_NK")
            log_id = f"{target}-NK-{int(cursor.fetchone()[0]):06d}"
            cursor.execute(
                "INSERT INTO dbo.Logs (ma_log, loai_log, ma_co_so, ma_tai_khoan, hanh_dong, bang_tac_dong, ma_ban_ghi, du_lieu_cu, du_lieu_moi, ip, ket_qua, ghi_chu) "
                "VALUES (%s, 'system', %s, NULL, 'doi_soat_blog_tu_authority', 'BaiVietBlog', %s, %s, %s, '', 'thanh_cong', %s)",
                [log_id, target, args.slug, json.dumps({c: len(str(target_row[c] or "")) for c in diff}), json.dumps({c: len(str(source_row[c] or "")) for c in diff}),
                 f"Chép bản của {authority} sang {target} bằng blog_reconcile.py"],
            )
    after = read(target, args.slug)
    print("Đã chép. Còn khác sau khi chép:", [c for c in COLUMNS if after[c] != source_row[c]] or "không")


if __name__ == "__main__":
    main()
