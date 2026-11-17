"""Browser smoke and interaction checks against the local Streamlit server."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root/"qa/browser"
out.mkdir(parents=True, exist_ok=True)
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1120}, device_scale_factor=1)
    page.goto("http://127.0.0.1:8501")
    page.get_by_role("heading", name="От интереса к заказу", exact=True).wait_for(timeout=30000)
    for name in ["Обзор", "Качество", "Бизнесы", "Маркет", "Экономика", "Концепция"]:
        page.get_by_test_id("stSidebar").get_by_text(name, exact=True).click()
        page.wait_for_timeout(1000)
        errors = page.locator('[data-testid="stException"]').count()
        assert errors == 0, (name, page.locator("body").inner_text())
        page.screenshot(path=str(out/f"{name}.png"), full_page=True)
        results.append({"section": name, "exceptions": errors, "screenshot": f"{name}.png"})
    browser.close()
(out/"results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(json.dumps(results, ensure_ascii=False, indent=2))
