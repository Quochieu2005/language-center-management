"""Cấp tài khoản cho học viên ở site không phải authority (EVB) qua giao diện admin thật, API chạy trên database tạm."""
import json
import os
import re

from playwright.sync_api import sync_playwright

WEB = "http://localhost:3001"
API_FROM = re.compile(r"^http://(localhost|127\.0\.0\.1):\d+/api/v1/")
API_TO = "http://localhost:8011/api/v1/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
PASSWORD = os.environ["SCRATCH_ADMIN_PASSWORD"]
TARGET = os.environ.get("TARGET_STUDENT", "HV EVB 1")
result = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1366, "height": 850}, locale="vi-VN")
    ctx.route("**/api/v1/**", lambda r: r.continue_(url=API_FROM.sub(API_TO, r.request.url)) if API_FROM.match(r.request.url) else r.continue_())
    page = ctx.new_page()
    calls = []
    def note(r):
        if "/api/v1/" in r.url and r.request.method != "GET":
            body = ""
            if r.status >= 400:
                try:
                    body = r.text()[:200]
                except Exception:  # noqa
                    pass
            calls.append(f"{r.request.method} {r.status} {r.url.split('/api/v1/')[-1][:70]} {body}")
    page.on("response", note)
    page.goto(WEB + "/login", wait_until="networkidle", timeout=60000)
    page.locator("input").nth(0).fill("admin_ev")
    page.locator("input[type=password]").first.fill(PASSWORD)
    page.get_by_role("button", name=re.compile("Đăng nhập", re.I)).first.click()
    page.wait_for_timeout(3500)
    page.goto(WEB + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    row = page.locator("tr", has_text=TARGET).first
    result["row_before"] = re.sub(r"\s+", " ", row.inner_text())
    row.get_by_role("button", name="Cấp tài khoản").click()
    page.wait_for_timeout(800)
    page.screenshot(path=os.path.join(OUT, "issue-confirm.png"))
    result["modal"] = re.sub(r"\s+", " ", page.locator(".ant-modal").inner_text())[:400]
    page.locator(".ant-modal").get_by_role("button", name="Cấp tài khoản").click()
    page.wait_for_timeout(5000)
    page.screenshot(path=os.path.join(OUT, "issue-after.png"))
    rows = page.locator("tr", has_text=TARGET)
    result["row_after"] = re.sub(r"\s+", " ", rows.first.inner_text()) if rows.count() else "(hàng đã biến mất khỏi danh sách chờ)"
    result["toast"] = re.sub(r"\s+", " ", " | ".join(page.locator(".ant-message").all_inner_texts()))[:300]
    result["write_calls"] = calls
    browser.close()
print(json.dumps(result, ensure_ascii=False, indent=1))
