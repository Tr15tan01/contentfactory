"""Phase 2 browser checks: guided setup, uploads (image, video, spoofed file), media library.

Run against a running stack:  python3 e2e/make_fixtures.py && python3 e2e/phase2.py
"""
import asyncio, os, re, sys, time, uuid
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
WORKER_LOG = os.environ.get("WORKER_LOG", "/tmp/worker.log")
FIX = os.environ.get("FIXTURES", "/tmp/e2e")
SHOTS = os.environ.get("SHOTS", "/tmp")
results = []

def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))

def token_for(email, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        m = re.findall(rf"--- email to {re.escape(email)} ---.*?/verify-email\?token=([A-Za-z0-9_\-]+)", open(WORKER_LOG).read(), re.S)
        if m: return m[-1]
        time.sleep(0.5)

async def main():
    email = f"p2-{uuid.uuid4().hex[:8]}@example.com"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(bypass_csp=True, viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        await page.goto(f"{BASE}/register")
        await page.fill("#full_name", "Ana Kapanadze"); await page.fill("#email", email); await page.fill("#password", "bakery-at-sunrise-9")
        await page.click("button[type=submit]")
        await expect(page.get_by_text("Check your inbox")).to_be_visible()
        await page.goto(f"{BASE}/verify-email?token={token_for(email)}")
        await page.wait_for_url("**/onboarding", timeout=10000)
        await expect(page.get_by_role("heading", name="Your business")).to_be_visible()
        check("verified user lands on step 1 of setup", True)

        # Step 1
        await page.fill("#biz-name", "Sunrise Bakery")
        await page.fill("#biz-industry", "Bakery")
        await page.fill("#biz-location", "Batumi, Georgia")
        await page.fill("#biz-website", "sunrise-bakery.ge")
        await page.fill("#biz-description", "Sourdough and pastries baked before dawn.")
        await page.screenshot(path=f"{SHOTS}/p2_step1.png")
        await page.click("text=Continue")
        await expect(page.get_by_role("heading", name="Customers and goals")).to_be_visible()
        check("step 1 saves and advances", True)

        # Step 2
        await page.click("text=More visits"); await page.click("text=Bring customers back")
        await page.fill("#aud-types", "Families"); await page.keyboard.press("Enter")
        await page.fill("#aud-usp", "Baked before dawn"); await page.keyboard.press("Enter")
        await page.click("text=Continue")
        await expect(page.get_by_role("heading", name="Brand voice")).to_be_visible()

        # Step 3
        await page.click("button:has-text('Warm')"); await page.click("button:has-text('Down-to-earth')")
        await page.fill("#brand-topics", "Politics"); await page.keyboard.press("Enter")
        await page.click("text=Add colour")
        await page.click("text=Continue")
        await expect(page.get_by_role("heading", name="Products and services")).to_be_visible()
        check("goals and brand steps save", True)

        # Step 4: product
        await page.fill("#prod-name", "Sourdough loaf"); await page.fill("#prod-price", "12,50")
        await page.click("text=Add product")
        await expect(page.get_by_text("12.50 USD")).to_be_visible()
        check("product added (comma decimal normalised)", True)
        await page.click("text=Continue")

        # Step 5: uploads (image, video, spoofed)
        await expect(page.get_by_role("heading", name="Photos and videos")).to_be_visible()
        await page.set_input_files("input[type=file]", [f"{FIX}/teal.png", f"{FIX}/bun.jpg", f"{FIX}/clip.mp4"])
        await expect(page.get_by_text("3 files in your library")).to_be_visible(timeout=20000)
        await page.wait_for_function("[...document.querySelectorAll('main img')].filter(i => i.complete && i.naturalWidth > 0).length >= 3", timeout=30000)
        check("uploads processed by worker and thumbnails shown", True)
        await page.screenshot(path=f"{SHOTS}/p2_step5.png")
        await page.click("text=Continue")

        # Step 6
        await expect(page.get_by_role("heading", name="Publishing")).to_be_visible()
        approval = page.locator("input[type=checkbox]")
        check("free plan cannot turn off approval", await approval.is_disabled())
        await page.click("button:has-text('Instagram')")
        await page.click("text=Continue")

        # Step 7
        await expect(page.get_by_role("heading", name="Review")).to_be_visible()
        await expect(page.get_by_text("3 in your library")).to_be_visible()
        body = await page.inner_text("main")
        check("review shows saved answers", all(s in body for s in ["Sunrise Bakery", "More visits", "Sourdough loaf", "3 in your library", "Instagram"]), body[:400])
        await page.screenshot(path=f"{SHOTS}/p2_review.png", full_page=True)
        await page.click("text=Finish setup")
        await page.wait_for_url("**/dashboard", timeout=10000)
        await expect(page.get_by_role("heading", level=1)).to_contain_text("Ana")
        dash = await page.inner_text("main")
        check("dashboard no longer asks to finish setup", "Finish setting up" not in dash)
        check("workspace renamed to business name", "Sunrise Bakery" in dash)

        # Media library: spoofed upload is rejected, edit tags, filter
        await page.goto(f"{BASE}/media")
        await expect(page.get_by_text("3 files")).to_be_visible()
        await page.set_input_files("input[type=file]", f"{FIX}/fake.png")
        await expect(page.get_by_text("Not added")).to_be_visible(timeout=20000)
        check("disguised file shown as not added", True)
        await page.get_by_role("button", name=re.compile("^bun")).click()
        await page.fill("#media-tags", "pastries"); await page.keyboard.press("Enter")
        await page.fill("#media-description", "Cardamom buns cooling")
        await page.get_by_role("button", name="Save", exact=True).click()
        await expect(page.get_by_role("dialog")).to_be_hidden()
        await page.get_by_role("button", name=re.compile("^pastries")).click()
        await expect(page.get_by_text("1 file", exact=True)).to_be_visible()
        check("tag edit and tag filter", True)
        await page.get_by_role("button", name=re.compile("^pastries")).click()
        await page.fill("input[placeholder^='Search']", "cooling")
        await expect(page.get_by_text("1 file", exact=True)).to_be_visible()
        check("search finds description text", True)
        await page.fill("input[placeholder^='Search']", "")
        await page.get_by_role("radio", name="Videos").click()
        await expect(page.get_by_text("1 file", exact=True)).to_be_visible()
        await page.get_by_role("radio", name="All").click()

        # Settings > Business shows the same data
        await page.goto(f"{BASE}/settings/business")
        await expect(page.locator("#biz-name")).to_have_value("Sunrise Bakery")
        check("settings business page loads saved profile", True)

        # Demo workspace media library
        demo = await browser.new_context(bypass_csp=True, viewport={"width": 1440, "height": 1000})
        dp = await demo.new_page()
        await dp.goto(f"{BASE}/login")
        await dp.fill("#email", "demo@contentfactory.dev"); await dp.fill("#password", "demo-coffee-2026")
        await dp.click("button[type=submit]"); await dp.wait_for_url("**/dashboard")
        await dp.goto(f"{BASE}/media")
        await expect(dp.get_by_text("6 files")).to_be_visible()
        await dp.wait_for_function("[...document.querySelectorAll('main img')].filter(i => i.complete && i.naturalWidth > 0).length >= 6", timeout=15000)
        check("demo library shows 6 real thumbnails", True)
        await dp.screenshot(path=f"{SHOTS}/p2_media_demo.png")
        await dp.get_by_role("button", name=re.compile("Cold brew bottles")).click()
        await expect(dp.get_by_role("dialog")).to_be_visible()
        await dp.screenshot(path=f"{SHOTS}/p2_media_detail.png")
        await demo.close()

        check("no uncaught page errors", not errors, "; ".join(errors[:3]))
        await browser.close()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)

asyncio.run(main())
