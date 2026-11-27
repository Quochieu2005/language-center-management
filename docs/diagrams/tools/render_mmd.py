"""Render the Mermaid sources to dark-theme SVG and PNG (light text on a dark background, pointed arrows)."""
import os, sys, json
from playwright.sync_api import sync_playwright

DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
names = sys.argv[1:] or ["erd-nghiep-vu", "erd-chuyen-co-so", "erd-xac-thuc", "erd-phu-tro", "bo-tri-vat-ly"]
BG = "#0d1117"
THEME = {
    "background": BG, "primaryColor": "#161b22", "primaryBorderColor": "#3b82f6", "primaryTextColor": "#f0f6fc",
    "secondaryColor": "#161b22", "tertiaryColor": "#161b22", "lineColor": "#9aa4b2", "textColor": "#f0f6fc",
    "edgeLabelBackground": BG, "clusterBkg": "#111722", "clusterBorder": "#30363d", "titleColor": "#f0f6fc",
    "fontFamily": "Segoe UI, Arial, sans-serif",
}
CSS = (".edgeLabel, .edgeLabel p, .edgeLabel span {color:#fbbf24 !important; background-color:" + BG + " !important;}"
       " .nodeLabel, .nodeLabel p {color:inherit !important;} .cluster-label span {color:#f0f6fc !important;}"
       " .marker {fill:#9aa4b2 !important; stroke:#9aa4b2 !important;}")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for name in names:
        src = open(os.path.join(DIR, name + ".mmd"), encoding="utf-8").read()
        page = b.new_page(viewport={"width": 1800, "height": 1200}, device_scale_factor=2)
        page.set_content("<html><body style='margin:0;background:%s'><div id='out' style='padding:24px;background:%s;display:inline-block'></div></body></html>" % (BG, BG))
        use_elk = src.lstrip().startswith("%%elk")
        if not use_elk:
            page.add_script_tag(url=MERMAID)
        svg = page.evaluate(
            """async ([src, theme, css, ELK_M, ELK_L]) => {
                const mermaid = window.mermaid || (await import(ELK_M)).default;
                if (!window.mermaid) { const elk = (await import(ELK_L)).default; mermaid.registerLayoutLoaders(elk); }
                mermaid.initialize({layout: window.mermaid ? undefined : 'elk', startOnLoad: false, theme: 'base', themeVariables: theme, themeCSS: css, securityLevel: 'loose',
                    flowchart: {htmlLabels: true, useMaxWidth: false, nodeSpacing: 50, rankSpacing: 80, curve: 'basis'}});
                const {svg} = await mermaid.render('d', src);
                document.getElementById('out').innerHTML = svg;
                return svg;
            }""", [src, THEME, CSS, "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs", "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.1.7/dist/mermaid-layout-elk.esm.min.mjs"])
        open(os.path.join(DIR, name + ".svg"), "w", encoding="utf-8").write(svg)
        box = page.locator("#out").bounding_box()
        page.set_viewport_size({"width": int(box["width"]) + 40, "height": int(box["height"]) + 40})
        page.locator("#out").screenshot(path=os.path.join(DIR, name + ".png"))
        print(name, "ok", round(box["width"]), "x", round(box["height"]))
        page.close()
    b.close()
