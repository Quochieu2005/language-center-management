"""Trang admin khi một site mất kết nối: đưa database tạm EVB về OFFLINE, xem Dashboard và Đăng ký khóa học, rồi bật lại."""
import json
import os
import re
import sys

import subprocess
from playwright.sync_api import sync_playwright  # noqa: E402

WEB = "http://localhost:3001"
API_FROM = re.compile(r"^http://(localhost|127\.0\.0\.1):\d+/api/v1/")
API_TO = "http://localhost:8011/api/v1/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
PASSWORD = os.environ["SCRATCH_ADMIN_PASSWORD"]
SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
VENV_PY = os.path.abspath(os.path.join(SCRIPTS, "..", "..", "..", "src", "api", ".venv", "Scripts", "python.exe"))
DB = "QLTTNN_EVB"


def set_state(state):
    """pyodbc chỉ có trong venv của API; Playwright chỉ có ở python hệ thống, nên đổi trạng thái qua venv."""
    code = (
        "import sys; sys.path.insert(0, %r);"
        "import ev_harness as h; h.connect('master').cursor().execute('ALTER DATABASE [%s] SET %s%s')"
    ) % (SCRIPTS, DB, state, " WITH ROLLBACK IMMEDIATE" if state == "OFFLINE" else "")
    subprocess.run([VENV_PY, "-c", code], check=True)


result = {}
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 850}, locale="vi-VN")
        ctx.route("**/api/v1/**", lambda r: r.continue_(url=API_FROM.sub(API_TO, r.request.url)) if API_FROM.match(r.request.url) else r.continue_())
        page = ctx.new_page()
        page.goto(WEB + "/login", wait_until="networkidle", timeout=60000)
        page.locator("input").nth(0).fill("admin_ev")
        page.locator("input[type=password]").first.fill(PASSWORD)
        page.get_by_role("button", name=re.compile("Đăng nhập", re.I)).first.click()
        page.wait_for_timeout(3500)
        set_state("OFFLINE")
        for name, path in (("outage-dashboard", "/admin"), ("outage-enrollments", "/admin/enrollments")):
            page.goto(WEB + path, wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2500)
            page.screenshot(path=os.path.join(OUT, name + ".png"), full_page=True)
            alerts = page.locator(".ant-alert").all_inner_texts()
            result[name] = {"alerts": [re.sub(r"\s+", " ", a) for a in alerts], "rows": page.locator("tbody tr").count()}
        browser.close()
finally:
    set_state("ONLINE")
print(json.dumps(result, ensure_ascii=False, indent=1))
