import os
import json, re, datetime
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3001"
CORS = {"Access-Control-Allow-Origin": BASE, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS"}
FUTURE = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
U = {"account_id": "T-1", "slug": "t", "email": "t@example.test", "username": "t", "role": "admin_big", "site_code": None, "profile_id": None, "must_change_password": False}


def handler(route):
    url = route.request.url
    path = (re.search(r"/api/v1/(.*?)(\?.*)?$", url) or [None, ""])[1]
    if route.request.method == "OPTIONS":
        return route.fulfill(status=204, headers=CORS)
    if path == "auth/session/":
        body = {"user": U, "expires_at": FUTURE}
    elif path == "auth/csrf/":
        body = {"csrf_token": "t"}
    else:
        body = {"results": [], "count": 0, "scope": "GLOBAL", "complete": True, "site_codes": ["Q1"], "missing_sites": [], "total_active_students": 0}
    route.fulfill(status=200, content_type="application/json", headers=CORS, body=json.dumps(body))


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for path in ("/admin/enrollments", "/admin/students", "/admin/notifications", "/admin/rooms", "/admin/audit"):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, locale="vi-VN")
        ctx.route("**/api/v1/**", handler)
        page = ctx.new_page()
        page.goto(BASE + path, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        side = page.evaluate("(() => { const s = document.querySelector('aside, [class*=sidebar]'); return s ? Math.round(s.getBoundingClientRect().width) : null; })()")
        print("%-22s overflow=%4dpx  sidebar_width=%s" % (path, over, side))
        ctx.close()
    b.close()
