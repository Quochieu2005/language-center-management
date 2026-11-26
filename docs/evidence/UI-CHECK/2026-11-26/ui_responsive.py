import json, os, re, datetime
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3001"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "screenshots")
os.makedirs(SHOTS, exist_ok=True)
CORS = {"Access-Control-Allow-Origin": BASE, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS"}
FUTURE = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
U = {"account_id": "T-1", "slug": "t", "email": "admin@example.test", "username": "admin", "role": "admin_big", "site_code": None, "profile_id": None, "must_change_password": False}
results = []


def check(name, ok, **kw):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name, kw or "")


def handler(route):
    url = route.request.url
    path = (re.search(r"/api/v1/(.*?)(\?.*)?$", url) or [None, ""])[1]
    if route.request.method == "OPTIONS":
        return route.fulfill(status=204, headers=CORS)
    if path == "auth/session/":
        body = {"user": U, "expires_at": FUTURE}
    elif path == "auth/csrf/":
        body = {"csrf_token": "t"}
    elif path.startswith("admin/reports/students-by-site"):
        body = {"scope": "GLOBAL", "complete": True, "missing_sites": [], "site_codes": ["Q1", "TD"], "total_active_students": 0, "results": []}
    else:
        body = {"results": [], "count": 0, "scope": "GLOBAL", "complete": True, "site_codes": ["Q1"], "missing_sites": []}
    route.fulfill(status=200, content_type="application/json", headers=CORS, body=json.dumps(body))


def new_page(b, w, h):
    ctx = b.new_context(viewport={"width": w, "height": h}, locale="vi-VN")
    ctx.route("**/api/v1/**", handler)
    page = ctx.new_page()
    return ctx, page


def sidebar_box(page):
    return page.evaluate("(() => { const r = document.querySelector('aside').getBoundingClientRect(); return {left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width)}; })()")


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)

    # ---- very narrow phones ----
    for w in (360, 320):
        ctx, page = new_page(b, w, 740)
        page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1000)
        over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        right = page.locator("button[title='Tài khoản']").bounding_box()
        check(f"{w}px: no horizontal overflow and user button inside viewport", over <= 1 and right["x"] + right["width"] <= w, overflow_px=over, right_edge=round(right["x"] + right["width"]))
        if w == 360:
            page.screenshot(path=f"{SHOTS}/phone-360.png")
        ctx.close()

    # ---- phone 390 ----
    for path in ("/admin/enrollments", "/admin/students", "/admin/notifications", "/admin/rooms", "/admin/audit"):
        ctx, page = new_page(b, 390, 844)
        page.goto(BASE + path, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1000)
        over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check(f"390px {path}: no horizontal overflow", over <= 1, overflow_px=over)
        ctx.close()

    ctx, page = new_page(b, 390, 844)
    page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1000)
    sb = sidebar_box(page)
    check("390px: drawer is hidden off-screen at first", sb["right"] <= 0, box=sb)
    check("390px: hidden drawer is inert (not focusable)", page.evaluate("document.querySelector('aside').inert === true"))
    avatar = page.locator("button[title='Tài khoản']").bounding_box()
    check("390px: user button stays inside the viewport", avatar["x"] + avatar["width"] <= 390, right_edge=round(avatar["x"] + avatar["width"]))
    page.screenshot(path=f"{SHOTS}/phone-closed.png")
    page.get_by_role("button", name=re.compile("sidebar", re.I)).click()
    page.wait_for_timeout(400)
    sb = sidebar_box(page)
    check("390px: toggle opens the drawer", sb["left"] == 0 and sb["width"] == 260, box=sb)
    check("390px: backdrop shown while open", page.locator("div[class*=backdrop]").count() == 1)
    check("390px: open drawer is not inert", page.evaluate("document.querySelector('aside').inert === false"))
    page.screenshot(path=f"{SHOTS}/phone-open.png")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    check("390px: Escape closes the drawer", sidebar_box(page)["right"] <= 0)
    page.get_by_role("button", name=re.compile("sidebar", re.I)).click()
    page.wait_for_timeout(300)
    page.mouse.click(350, 400)
    page.wait_for_timeout(400)
    check("390px: tapping the backdrop closes the drawer", sidebar_box(page)["right"] <= 0)
    page.get_by_role("button", name=re.compile("sidebar", re.I)).click()
    page.wait_for_timeout(300)
    page.get_by_role("link", name="Phòng học").click()
    page.wait_for_url("**/admin/rooms", timeout=15000)
    page.wait_for_timeout(500)
    check("390px: choosing a menu item navigates and closes the drawer", sidebar_box(page)["right"] <= 0 and page.url.endswith("/admin/rooms"))
    ctx.close()

    # ---- tablet 768 and just above ----
    ctx, page = new_page(b, 768, 1024)
    page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(800)
    check("768px: drawer mode, no overflow", sidebar_box(page)["right"] <= 0 and page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1)
    page.screenshot(path=f"{SHOTS}/tablet-768.png")
    ctx.close()
    ctx, page = new_page(b, 769, 1024)
    page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(800)
    check("769px: fixed sidebar visible (desktop layout)", sidebar_box(page)["width"] == 260 and sidebar_box(page)["left"] == 0, box=sidebar_box(page))
    ctx.close()

    # ---- desktop unchanged ----
    ctx, page = new_page(b, 1440, 900)
    page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(800)
    check("1440px: sidebar visible at 260px", sidebar_box(page)["width"] == 260)
    page.get_by_role("button", name=re.compile("sidebar", re.I)).click()
    page.wait_for_timeout(500)
    check("1440px: toggle still collapses to 72px", sidebar_box(page)["width"] == 72, box=sidebar_box(page))
    check("1440px: no backdrop on desktop", page.locator("div[class*=backdrop]").count() == 0)
    page.screenshot(path=f"{SHOTS}/desktop-collapsed.png")
    ctx.close()

    # ---- resize across the breakpoint with the drawer open ----
    ctx, page = new_page(b, 390, 844)
    page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(800)
    page.get_by_role("button", name=re.compile("sidebar", re.I)).click()
    page.wait_for_timeout(300)
    page.set_viewport_size({"width": 1200, "height": 800})
    page.wait_for_timeout(500)
    check("resize 390 -> 1200 with drawer open: desktop layout, no backdrop", sidebar_box(page)["width"] == 260 and page.locator("div[class*=backdrop]").count() == 0, box=sidebar_box(page))
    ctx.close()
    b.close()

print("FAILED:", [n for n, ok in results if not ok])
