"""Read-only audit of the project's Cloudinary images: which ones no site references any more.

Lists every image under ``CLOUDINARY_ROOT_FOLDER`` (Cloudinary Admin API) and compares it with the ``public_id`` values
stored in the site databases (avatars, blog covers) plus Cloudinary URLs inside blog article bodies. It never deletes or
changes anything, and never prints credentials.

    src/api/.venv/Scripts/python.exe db/tools/cloudinary_audit.py
    src/api/.venv/Scripts/python.exe db/tools/cloudinary_audit.py --out orphans.json

Read the verdict per site: an image counts as an orphan only for the sites that could be read. When a site is
unreachable the orphan list is only a CANDIDATE list; delete nothing until every site has been read.
Images stored outside the root folder (older UUID-style ids) are reported as "outside root" and are never candidates.
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
API = os.path.join(ROOT, "src", "api")
os.chdir(API)
sys.path.insert(0, API)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.db import connections  # noqa: E402

from core.sites.connections import get_site_database_alias  # noqa: E402

REFERENCE_COLUMNS = (
    ("TaiKhoan", "avatar_public_id"), ("HocVien", "avatar_public_id"), ("GiaoVien", "avatar_public_id"),
    ("NhanVien", "avatar_public_id"), ("NguoiDung", "avatar_public_id"), ("BaiVietBlog", "anh_bia_public_id"),
)


def list_assets(root):
    cloud, key, secret = settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, settings.CLOUDINARY_API_SECRET
    if not (cloud and key and secret and root):
        sys.exit("Thiếu cấu hình Cloudinary (CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET/ROOT_FOLDER) trong src/api/.env.")
    auth = "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()
    assets, cursor = {}, None
    while True:
        query = {"type": "upload", "prefix": root, "max_results": 500}
        if cursor:
            query["next_cursor"] = cursor
        url = f"https://api.cloudinary.com/v1_1/{cloud}/resources/image?" + urllib.parse.urlencode(query)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": auth}), timeout=30) as resp:
            data = json.loads(resp.read())
        for item in data.get("resources", []):
            assets[item["public_id"]] = {"kb": item.get("bytes", 0) // 1024, "created": item.get("created_at", "")[:10]}
        cursor = data.get("next_cursor")
        if not cursor:
            return assets


def collect_references(root):
    """Return (references: public_id -> set of 'SITE:Table', read_sites, unreachable_sites)."""
    refs, read, unreachable = {}, [], []
    body_pattern = re.compile(r"res\.cloudinary\.com/[^/]+/image/upload/(?:[^/]+/)*?(%s/[^\s\"')?]+)" % re.escape(root))
    for site in sorted(settings.SITE_DATABASE_ALIASES):
        try:
            with connections[get_site_database_alias(site)].cursor() as cursor:
                for table, column in REFERENCE_COLUMNS:
                    try:
                        cursor.execute(f"SELECT {column} FROM dbo.{table} WHERE {column} IS NOT NULL")
                    except Exception:  # table or column absent on this site's schema version
                        continue
                    for (value,) in cursor.fetchall():
                        refs.setdefault(value, set()).add(f"{site}:{table}")
                try:
                    cursor.execute("SELECT noi_dung FROM dbo.BaiVietBlog")
                    for (body,) in cursor.fetchall():
                        for found in body_pattern.findall(body or ""):
                            refs.setdefault(re.sub(r"\.[A-Za-z0-9]+$", "", found), set()).add(f"{site}:BaiVietBlog.noi_dung")
                except Exception:
                    pass
            read.append(site)
        except Exception:
            unreachable.append(site)
    return refs, read, unreachable


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="ghi danh sách ứng viên mồ côi ra file JSON")
    args = parser.parse_args()

    root = settings.CLOUDINARY_ROOT_FOLDER.strip("/ ")
    assets = list_assets(root)
    refs, read, unreachable = collect_references(root)
    in_use = sorted(set(assets) & set(refs))
    orphans = sorted(set(assets) - set(refs))
    outside = sorted(p for p in refs if not p.startswith(root + "/"))
    dangling = sorted(p for p in refs if p.startswith(root + "/") and p not in assets)

    print(f"Ảnh dưới thư mục gốc: {len(assets)} ({sum(a['kb'] for a in assets.values())} KB)")
    print(f"Site đọc được: {read or '—'} | không đọc được: {unreachable or '—'}")
    print(f"Đang được tham chiếu: {len(in_use)} | ứng viên mồ côi: {len(orphans)} | "
          f"tham chiếu ngoài thư mục gốc (không động tới): {len(outside)} | tham chiếu trỏ tới ảnh không còn: {len(dangling)}")
    if unreachable:
        print("CẢNH BÁO: còn site chưa đọc được; danh sách mồ côi chỉ là ỨNG VIÊN, chưa được xóa gì.")
    for public_id in orphans:
        print(f"  mồ côi: {public_id} ({assets[public_id]['kb']} KB, {assets[public_id]['created']})")
    for public_id in dangling:
        print(f"  tham chiếu hỏng: {public_id} ({', '.join(sorted(refs[public_id]))})")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"orphans": orphans, "unreachable_sites": unreachable, "outside_root_references": outside,
                       "dangling_references": dangling}, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
