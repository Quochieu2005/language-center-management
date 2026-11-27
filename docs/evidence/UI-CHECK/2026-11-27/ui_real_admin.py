"""Kiểm tra giao diện admin với API thật chạy trên hai database tạm (EVA authority, EVB), tài khoản admin_big thật.

Web dùng cổng 3001 và gọi API ở một origin cố định; kịch bản chuyển hướng các yêu cầu /api/v1 sang API tạm (cổng 8011).
Không đụng Q1, Q7, TD. Mật khẩu của tài khoản tạm đọc từ biến môi trường SCRATCH_ADMIN_PASSWORD.
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

WEB = "http://localhost:3001"
API_FROM = re.compile(r"^http://(localhost|127\.0\.0\.1):\d+/api/v1/")
API_TO = "http://localhost:8011/api/v1/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT, exist_ok=True)
PASSWORD = os.environ["SCRATCH_ADMIN_PASSWORD"]
PAGES = [("dashboard", "/admin"), ("enrollments", "/admin/enrollments")] + [(p.strip("/").replace("/", "-"), p) for p in sys.argv[1:]]
result = {}


def reroute(route):
    url = route.request.url
    if API_FROM.match(url):
        route.continue_(url=API_FROM.sub(API_TO, url))
    else:
        route.continue_()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1366, "height": 850}, locale="vi-VN")
    ctx.route("**/api/v1/**", reroute)
    page = ctx.new_page()
    seen = []
    page.on("response", lambda r: seen.append((r.status, r.url.split("/api/v1/")[-1][:60])) if "/api/v1/" in r.url else None)
    page.goto(WEB + "/login", wait_until="networkidle", timeout=60000)
    page.locator("input").nth(0).fill("admin_ev")
    page.locator("input[type=password]").first.fill(PASSWORD)
    page.get_by_role("button", name=re.compile("Đăng nhập", re.I)).first.click()
    page.wait_for_timeout(4000)
    result["after_login_url"] = page.url
    for name, path in PAGES:
        seen.clear()
        page.goto(WEB + path, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(OUT, name + ".png"), full_page=True)
        text = page.inner_text("body")
        result[name] = {"url": page.url, "api": [f"{s} {u}" for s, u in seen], "text_head": re.sub(r"\s+", " ", text)[:600]}
    browser.close()
print(json.dumps(result, ensure_ascii=False, indent=1))
