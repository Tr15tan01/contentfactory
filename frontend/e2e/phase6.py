"""Phase 6 browser checks on the demo business: analytics, insights, memory, experiments.

Needs the demo seed (python -m scripts.seed_demo) and a running stack.
"""
import asyncio, os, re, sys, uuid
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
SHOTS = os.environ.get("SHOTS", "/tmp")
RUN = uuid.uuid4().hex[:6]
results = []

def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(viewport={"width": 1440, "height": 1000})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{BASE}/login")
        await page.fill("#email", "demo@contentfactory.dev"); await page.fill("#password", "demo-coffee-2026")
        await page.click("button[type=submit]"); await page.wait_for_url("**/dashboard")

        await page.goto(f"{BASE}/analytics")
        await expect(page.get_by_role("heading", name="Engagements per day")).to_be_visible()
        body = await page.inner_text("main")
        check("analytics shows measured posts and KPIs", "posts published" in body and "Reach" in body and "Top posts" in body, body[:200])
        await page.get_by_role("radio", name="90 days").click()
        await expect(page.get_by_text("posts published", exact=False)).to_be_visible()
        check("period switch works", True)
        await page.screenshot(path=f"{SHOTS}/p6_analytics.png", full_page=True)

        await page.goto(f"{BASE}/insights")
        await expect(page.get_by_text("Educational posts averaged").first).to_be_visible()
        check("seeded insight shown with evidence", await page.get_by_text("Based on", exact=False).count() >= 1)
        await page.get_by_role("button", name="Analyse now").click()
        await expect(page.get_by_text("Analysis finished")).to_be_visible()
        check("analysis runs from the page", True)
        remember = page.get_by_role("button", name="Remember this").first
        if await remember.count():
            await remember.click()
            await expect(page.get_by_text("In your agent's memory").first).to_be_visible()
        check("an insight can be saved to memory", await page.get_by_text("In your agent's memory").count() >= 1)
        await page.screenshot(path=f"{SHOTS}/p6_insights.png", full_page=True)

        # Experiment (demo is on Business)
        await page.get_by_role("button", name="New experiment").click()
        await page.fill("#exp-name", f"Question hooks {RUN}"); await page.fill("#exp-hyp", "Questions get more comments")
        await page.fill("#exp-a", "Hook is a question"); await page.fill("#exp-b", "Hook is a statement")
        await page.get_by_role("button", name="Start experiment").click()
        card = page.locator("article").filter(has_text=f"Question hooks {RUN}")
        await expect(card).to_be_visible()
        await card.get_by_role("button", name="Choose posts").first.click()
        boxes = page.get_by_role("dialog").locator("input[type=checkbox]")
        await boxes.nth(0).check(); await boxes.nth(1).check()
        await page.get_by_role("dialog").get_by_role("button", name=re.compile(r"Use 2 posts")).click()
        await expect(card.get_by_text("2 posts assigned")).to_be_visible()
        await card.get_by_role("button", name="Check results").click()
        await expect(card.get_by_text("Still collecting")).to_be_visible()
        check("experiment created, posts assigned, honest 'still collecting'", True)
        await card.get_by_role("button", name="Stop").click()
        await expect(card.get_by_text("Cancelled")).to_be_visible()

        # Memory
        await page.goto(f"{BASE}/intelligence/memory")
        await page.fill("#mem-content", f"Students from the university nearby come in after 4pm ({RUN})")
        await page.get_by_role("button", name="Add").click()
        await expect(page.get_by_text(f"after 4pm ({RUN})")).to_be_visible()
        await page.fill("input[placeholder^='Search']", "university students")
        await expect(page.locator("main ul li").first).to_contain_text("university nearby")
        check("memory added and found by search", True)
        row = page.locator("li").filter(has_text=f"({RUN})")
        await row.get_by_role("button", name="Always use").click()
        await expect(row.get_by_text("Always used")).to_be_visible()
        check("memory can be pinned", True)
        await page.fill("input[placeholder^='Search']", "")
        await page.screenshot(path=f"{SHOTS}/p6_memory.png", full_page=True)

        check("no uncaught page errors", not errors, "; ".join(errors[:3]))
        await browser.close()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)

asyncio.run(main())
