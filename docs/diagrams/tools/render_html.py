import os
from playwright.sync_api import sync_playwright

DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
    page.goto("file:///" + os.path.join(DIR, "dinh-vi-du-lieu.html").replace("\\", "/"))
    page.wait_for_timeout(300)
    el = page.locator("#diagram")
    el.screenshot(path=os.path.join(DIR, "dinh-vi-du-lieu.png"))
    box = el.bounding_box()
    print("ok", round(box["width"]), "x", round(box["height"]))
    b.close()
