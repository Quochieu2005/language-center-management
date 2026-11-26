import json, os, re, sys, datetime
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3001"
CORS = {"Access-Control-Allow-Origin": "http://localhost:3001", "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS"}
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "screenshots")
os.makedirs(SHOTS, exist_ok=True)
FUTURE = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
report = []
unmatched = set()


def note(name, **kw):
    report.append({"check": name, **kw})
    flag = kw.get("ok")
    print(("PASS " if flag is True else "FAIL " if flag is False else "INFO ") + name, {k: v for k, v in kw.items() if k != "ok"})


def user(role, site=None, **kw):
    return {"account_id": "TEST-TK-1", "slug": "tai-khoan-thu", "email": "thu@example.test", "username": "thu", "role": role,
            "site_code": site, "profile_id": None, "must_change_password": False, "avatar_secure_url": None, **kw}


def reg_rows():
    t = "2026-11-25T09:30:00+07:00"
    base = dict(enrollment_status="dang_hoc", class_id="Q1-LH-000001", class_name="IELTS 6.5 Tối", course_name="IELTS 6.5", phone="0901234567")
    return [
        {**base, "enrollment_id": "Q1-DK-1", "enrolled_at": t, "student_id": "Q1-HV-1", "slug": "nguyen-van-an", "site_code": "Q1", "full_name": "Nguyễn Văn An",
         "email": "an@example.test", "account_issued": False, "account_issue_eligible": True, "has_website_account": True},
        {**base, "enrollment_id": "TD-DK-1", "enrolled_at": t, "student_id": "TD-HV-1", "slug": "tran-thi-binh", "site_code": "TD", "full_name": "Trần Thị Bình",
         "email": "binh@example.test", "account_issued": False, "account_issue_eligible": True, "has_website_account": False, "course_name": "TOEIC 450-550", "class_name": "TOEIC Sáng"},
        {**base, "enrollment_id": "Q1-DK-2", "enrolled_at": t, "student_id": "Q1-HV-2", "slug": "le-minh-chau", "site_code": "Q1", "full_name": "Lê Minh Châu",
         "email": "chau@example.test", "account_issued": True, "account_issue_eligible": False, "has_website_account": False},
        {**base, "enrollment_id": "Q1-DK-3", "enrolled_at": t, "student_id": "Q1-HV-3", "slug": "pham-huu-dung", "site_code": "Q1", "full_name": "Phạm Hữu Dũng",
         "email": None, "phone": None, "account_issued": False, "account_issue_eligible": False, "has_website_account": None},
    ]


COURSE = {"course_id": "KH-1", "slug": "luyen-thi-toeic-450-550", "subject_id": "MH-1", "subject_slug": "tieng-anh", "subject_name": "Tiếng Anh",
          "name": "Luyện thi TOEIC 450 - 550", "level": "A2", "session_count": 24, "thoi_luong_so": 3, "thoi_luong_don_vi": "thang",
          "standard_fee": 4500000, "version": 1,
          "branches": [{"site_code": "Q1", "site_name": "Cơ sở Quận 1", "open_class_count": 2}, {"site_code": "TD", "site_name": "Cơ sở Thủ Đức", "open_class_count": 1}]}


def install_mocks(ctx, role, site, mode="rows", catalog=False):
    def handler(route):
        req = route.request
        url = req.url
        m = re.search(r"/api/v1/(.*?)(\?.*)?$", url)
        path = m.group(1) if m else ""
        q = dict(p.split("=", 1) for p in (m.group(2) or "?")[1:].split("&") if "=" in p) if m else {}
        if req.method == "OPTIONS" and ("/api/v1/auth/" in url or "/api/v1/admin/" in url):
            return route.fulfill(status=204, headers=CORS)
        def ok(body, status=200):
            route.fulfill(status=status, content_type="application/json", headers=CORS, body=json.dumps(body, ensure_ascii=False))
        if path == "auth/session/":
            if role is None:
                return route.fulfill(status=204, headers=CORS)
            return ok({"user": user(role, site), "expires_at": FUTURE})
        if catalog and path == "courses/":
            return ok({"scope": "GLOBAL", "complete": True, "site_codes": ["Q1", "TD"], "missing_sites": [], "inconsistent_sites": [], "count": 1, "results": [COURSE]})
        if catalog and re.fullmatch(r"courses/[^/]+/classes/", path):
            sc = q.get("site_code", "Q1")
            return ok({"site_code": sc, "course_slug": COURSE["slug"], "count": 2, "results": [
                {"class_id": sc + "-LH-1", "site_code": sc, "name": "TOEIC Tối T2-4-6", "start_date": "2026-12-08", "end_date": "2027-03-08", "schedule": "T2-T4-T6", "start_time": "18:30", "end_time": "20:30", "remaining_seats": 12},
                {"class_id": sc + "-LH-2", "site_code": sc, "name": "TOEIC Sáng T3-5", "start_date": "2026-12-15", "end_date": None, "schedule": "T3-T5", "start_time": "08:00", "end_time": "10:00", "remaining_seats": 3}]})
        if catalog and path == "public/enrollments/":
            return ok({"site_code": "Q1", "class_id": "Q1-LH-1", "accepted": True, "already_registered": False, "message": "Đã nhận đăng ký"}, 201)
        if path == "auth/csrf/":
            return ok({"csrf_token": "test"})
        if path.startswith("admin/reports/students-by-site"):
            return ok({"scope": "GLOBAL", "complete": False, "missing_sites": ["Q7"], "site_codes": ["Q1", "TD"], "total_active_students": 3,
                       "results": [{"site_code": "Q1", "active_students": 2}, {"site_code": "TD", "active_students": 1}]})
        if path == "admin/course-registrations/":
            if mode == "error":
                return ok({"detail": "Không đọc được dữ liệu đăng ký từ cơ sở."}, 503)
            rows = [] if mode == "empty" else reg_rows()
            if q.get("pending", "true") == "true":
                rows = [r for r in rows if not r["account_issued"]]
            if role == "admin_big":
                return ok({"scope": "GLOBAL", "complete": False, "site_codes": ["Q1", "TD"], "missing_sites": ["Q7"], "count": len(rows), "limit": 100, "offset": 0, "results": rows})
            return ok({"site_code": site, "count": len(rows), "limit": 100, "offset": 0, "results": [r for r in rows if r["site_code"] == site]})
        if path == "auth/account-profile/":
            if req.method == "PATCH":
                body = json.loads(req.post_data or "{}")
                return ok({"slug": "tai-khoan-thu", "email": "thu@example.test", "username": "thu", "full_name": body.get("full_name", "Thử"), "birth_date": None,
                           "gender": None, "phone": body.get("phone"), "address": body.get("address"), "avatar_secure_url": None})
            return ok({"slug": "tai-khoan-thu", "email": "thu@example.test", "username": "thu", "full_name": "Người Dùng Thử", "birth_date": "2000-01-02",
                       "gender": "Nam", "phone": "0900000000", "address": "1 Nguyễn Huệ", "avatar_secure_url": None})
        if "/api/v1/auth/" in url or "/api/v1/admin/" in url:
            unmatched.add(req.method + " " + path)
            return ok({"results": [], "count": 0})
        route.continue_()
    ctx.route("**/api/v1/**", handler)


def collect(page, bucket):
    page.on("console", lambda m: bucket.append(m.text[:160]) if m.type == "error" else None)
    page.on("pageerror", lambda e: bucket.append("pageerror: " + str(e)[:160]))



def wait_or_dump(page, text, tag, errs=None):
    try:
        page.wait_for_selector("text=" + text, timeout=20000)
    except Exception:
        page.screenshot(path=f"{SHOTS}/FAIL-{tag}.png", full_page=True)
        body = " | ".join(page.inner_text("body").splitlines())[:500]
        print("WAIT FAILED", tag, "| url:", page.url, "| body:", body, "| errs:", (errs or [])[:4], "| unmatched:", sorted(unmatched))
        raise

def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - window.innerWidth")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    def new_ctx(w=1440, h=900, role=None, site=None, mode="rows", catalog=False):
        ctx = browser.new_context(viewport={"width": w, "height": h}, locale="vi-VN")
        if role or catalog:
            install_mocks(ctx, role, site, mode, catalog)
        return ctx

    # ---------- Blog (real API) ----------
    for label, w, h in (("desktop", 1440, 900), ("mobile", 390, 844)):
        ctx = new_ctx(w, h); page = ctx.new_page(); errs = []; collect(page, errs)
        page.goto(BASE + "/blog", wait_until="networkidle", timeout=60000)
        page.screenshot(path=f"{SHOTS}/blog-list-{label}.png", full_page=True)
        note(f"blog list {label}: no horizontal overflow", ok=overflow(page) <= 1, overflow_px=overflow(page), console_errors=len(errs))
        page.goto(BASE + "/blog/bat-dau-hoc-ngoai-ngu", wait_until="networkidle", timeout=60000)
        page.screenshot(path=f"{SHOTS}/blog-detail-{label}.png", full_page=True)
        body = page.inner_text("body")
        note(f"blog detail {label}: no overflow", ok=overflow(page) <= 1, overflow_px=overflow(page))
        note(f"blog detail {label}: eyebrow/reading-time 'Bắt đầu đọc' removed", ok="bắt đầu đọc" not in body.lower())
        ctx.close()

    # ---------- Admin Big: course registrations ----------
    ctx = new_ctx(1440, 900, "admin_big", None); page = ctx.new_page(); errs = []; collect(page, errs)
    page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    wait_or_dump(page, "Nguyễn Văn An", "enroll-admin-big", errs)
    page.screenshot(path=f"{SHOTS}/enroll-admin-big.png", full_page=True)
    alert = page.locator(".ant-alert").first
    card = page.locator(".ant-card").first
    aw, cw = alert.bounding_box()["width"], card.bounding_box()["width"]
    note("enrollments: warning alert fills the card width", ok=aw >= cw * 0.9, alert_px=round(aw), card_px=round(cw))
    note("enrollments: alert text names the offline site", ok="Q7" in alert.inner_text(), text=alert.inner_text()[:120])
    txt = page.inner_text("body")
    note("enrollments: pending-only hides the already-issued student", ok="Lê Minh Châu" not in txt)
    note("enrollments: both account tags present", ok=("Đã đăng ký trên website" in txt and "Chưa có tài khoản" in txt))
    note("enrollments: sidebar item present", ok="Đăng ký khóa học" in txt)
    page.get_by_role("button", name="Cấp tài khoản").first.click()
    page.wait_for_selector(".ant-modal", timeout=5000)
    mt = page.locator(".ant-modal").inner_text()
    note("enrollments: confirm modal explains password is kept for website accounts", ok="giữ nguyên mật khẩu" in mt, text=mt[:130].replace("\n", " "))
    page.screenshot(path=f"{SHOTS}/enroll-modal.png")
    page.get_by_role("button", name="Hủy").click()
    page.locator(".ant-switch").first.click()
    page.wait_for_selector("text=Lê Minh Châu", timeout=10000)
    txt = page.inner_text("body")
    note("enrollments: switch off shows issued student with 'Đã cấp'", ok=("Đã cấp" in txt))
    disabled = page.get_by_role("button", name="Cấp tài khoản").evaluate_all("els => els.map(e => e.disabled)")
    note("enrollments: student without email has a disabled issue button", ok=any(disabled), disabled_flags=disabled)
    page.screenshot(path=f"{SHOTS}/enroll-all.png", full_page=True)
    note("enrollments admin_big: console errors", ok=len(errs) == 0, errors=errs[:3])
    ctx.close()

    for mode in ("empty", "error"):
        ctx = new_ctx(1440, 900, "admin_big", None, mode); page = ctx.new_page(); errs = []; collect(page, errs)
        page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{SHOTS}/enroll-{mode}.png", full_page=True)
        note(f"enrollments {mode} state renders", ok=True, text=page.inner_text(".ant-card").replace("\n", " | ")[:200])
        ctx.close()

    # mobile + Tu van
    ctx = new_ctx(390, 844, "tu_van", "Q1"); page = ctx.new_page(); errs = []; collect(page, errs)
    page.goto(BASE + "/admin/enrollments", wait_until="networkidle", timeout=60000)
    wait_or_dump(page, "Nguyễn Văn An", "enroll-tuvan", errs)
    page.screenshot(path=f"{SHOTS}/enroll-tuvan-mobile.png", full_page=True)
    txt = page.inner_text("body")
    note("enrollments tu_van: view-only message, no issue button", ok=("Chờ Admin cấp tài khoản" in txt and page.get_by_role("button", name="Cấp tài khoản").count() == 0))
    note("enrollments mobile: page itself has no horizontal overflow (table scrolls inside card)", ok=overflow(page) <= 1, overflow_px=overflow(page))
    ctx.close()

    # ---------- /account as nguoi_dung ----------
    ctx = new_ctx(1440, 900, "nguoi_dung", None); page = ctx.new_page(); errs = []; collect(page, errs)
    page.goto(BASE + "/account", wait_until="networkidle", timeout=60000)
    page.wait_for_selector("text=Người Dùng Thử", timeout=20000) if page.locator("text=Người Dùng Thử").count() else page.wait_for_timeout(1500)
    page.screenshot(path=f"{SHOTS}/account-user.png", full_page=True)
    note("account page: loads profile for nguoi_dung", ok=("thu@example.test" in page.inner_text("body")), console_errors=errs[:2])
    ctx.close()

    # ---------- Enrollment dialog: nguoi_dung (mock session) and guest (real) ----------
    for label, role in (("user", "nguoi_dung"), ("guest", None)):
        ctx = new_ctx(1440, 900, role, None, catalog=True); page = ctx.new_page(); errs = []; collect(page, errs)
        page.goto(BASE + "/courses/luyen-thi-toeic-450-550", wait_until="networkidle", timeout=60000)
        btn = page.get_by_role("button", name=re.compile("Đăng ký", re.I))
        if btn.count() == 0:
            note(f"enroll dialog {label}: no register button found", ok=False)
        else:
            btn.first.click()
            page.wait_for_selector(".ant-modal", timeout=10000)
            page.wait_for_timeout(1500)
            page.screenshot(path=f"{SHOTS}/enroll-dialog-{label}.png")
            m = page.locator(".ant-modal")
            if role:
                email = m.locator("input[type=email], input[id*=email]").first
                note("enroll dialog (website user): email prefilled and read-only",
                     ok=bool(email.count()) and email.input_value() == "thu@example.test" and (email.get_attribute("readonly") is not None or email.is_disabled()),
                     value=email.input_value() if email.count() else None)
            note(f"enroll dialog {label}: opens", ok=True, text=m.inner_text().replace("\n", " | ")[:180])
        ctx.close()
    browser.close()

json.dump({"report": report, "unmatched_mock_endpoints": sorted(unmatched)}, open(os.path.join(SHOTS, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("unmatched mocked endpoints:", sorted(unmatched))
print("FAILED:", [r["check"] for r in report if r.get("ok") is False])
