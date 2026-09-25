"""End-to-end smoke test against a running stack (Next :3000, FastAPI :8000, arq worker).

Run:  python3 e2e/smoke.py   (WORKER_LOG defaults to /tmp/worker.log; dev console email provider)
"""
import asyncio, os, re, sys, time, uuid
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
WORKER_LOG = os.environ.get("WORKER_LOG", "/tmp/worker.log")
SHOTS = os.environ.get("SHOTS", "/tmp")
results = []

def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))

def token_for(email, kind, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = open(WORKER_LOG).read()
        m = re.findall(rf"--- email to {re.escape(email)} ---.*?/{kind}\?token=([A-Za-z0-9_\-]+)", text, re.S)
        if m: return m[-1]
        time.sleep(0.5)
    return None

async def main():
    email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
    pw1, pw2 = "espresso-at-dawn-42", "cold-brew-by-noon-77"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # Signed-out visitors are sent to login with a return path.
        await page.goto(f"{BASE}/settings/security")
        check("protected page redirects to login", "/login?next=%2Fsettings%2Fsecurity" in page.url, page.url)

        # Register -> check inbox state
        await page.goto(f"{BASE}/register")
        await page.fill("#full_name", "Tamar Beridze")
        await page.fill("#email", email)
        await page.fill("#password", pw1)
        await page.click("button[type=submit]")
        await expect(page.get_by_text("Check your inbox")).to_be_visible()
        check("register shows check-inbox", True)

        # Verification email -> signed in -> onboarding
        token = token_for(email, "verify-email")
        check("verification email delivered by worker", token is not None)
        await page.goto(f"{BASE}/verify-email?token={token}")
        await page.wait_for_url("**/onboarding", timeout=10000)
        check("verify link signs in and opens onboarding", page.url.endswith("/onboarding"))

        # Dashboard for a brand-new account
        await page.goto(f"{BASE}/dashboard")
        await expect(page.get_by_role("heading", level=1)).to_contain_text("Tamar")
        body = await page.inner_text("main")
        check("new dashboard asks to finish setup", "Finish setting up" in body or "set up" in body.lower(), body[:300])
        check("new dashboard shows no fake insights", "No conclusions yet" in body)
        await page.screenshot(path=f"{SHOTS}/e2e_dash_new.png", full_page=True)

        # Change password; the session list shows this device
        await page.goto(f"{BASE}/settings/security")
        await expect(page.get_by_text("This device")).to_be_visible()
        await page.fill("#current_password", pw1)
        await page.fill("#new_password", pw2)
        await page.fill("#confirm", pw2)
        await page.click("text=Change password >> nth=-1")
        await expect(page.get_by_text("Password changed")).to_be_visible()
        check("change password", True)

        # Sign out from the account menu
        await page.click("[aria-label='Account menu']")
        await page.get_by_role("menuitem", name="Sign out").click()
        await page.wait_for_url("**/login", timeout=10000)
        check("sign out", True)

        # Wrong password, then the new password works and honours ?next
        await page.goto(f"{BASE}/login?next=/settings")
        await page.fill("#email", email); await page.fill("#password", pw1)
        await page.click("button[type=submit]")
        await expect(page.get_by_text("Email or password is incorrect")).to_be_visible()
        check("wrong password rejected", True)
        await page.fill("#password", pw2)
        await page.click("button[type=submit]")
        await page.wait_for_url(re.compile(r"^[^?]*/settings$"), timeout=10000)
        check("login honours next", page.url.endswith("/settings"))

        # Open-redirect attempt is ignored
        await page.goto(f"{BASE}/login?next=//evil.example.com")
        check("login page loads with hostile next", "/login" in page.url)

        # /analytics: app page when signed in, marketing page when signed out
        await page.goto(f"{BASE}/analytics")
        try:
            await expect(page.get_by_text("Performance of published posts")).to_be_visible(timeout=10000)
            check("signed-in /analytics shows workspace analytics", page.url.endswith("/analytics"))
        except AssertionError:
            check("signed-in /analytics shows workspace analytics", False, page.url)
        anon = await browser.new_context()
        ap = await anon.new_page(); await ap.goto(f"{BASE}/analytics")
        check("public /analytics shows marketing page", await ap.get_by_role("heading", level=1).inner_text() == "Social media analytics that tell you what to do next")
        await anon.close()

        # Demo workspace with real seeded data (light and dark)
        demo = await browser.new_context(viewport={"width": 1440, "height": 1000})
        dp = await demo.new_page()
        await dp.goto(f"{BASE}/login")
        await dp.fill("#email", "demo@contentfactory.dev"); await dp.fill("#password", "demo-coffee-2026")
        await dp.click("button[type=submit]")
        await dp.wait_for_url("**/dashboard", timeout=10000)
        await expect(dp.get_by_text("Demo data")).to_be_visible()
        demo_text = await dp.inner_text("main")
        check("demo dashboard shows computed insight", "Educational posts averaged" in demo_text)
        check("demo dashboard shows upcoming posts", "Upcoming" in demo_text and "Awaiting approval" in demo_text)
        await dp.screenshot(path=f"{SHOTS}/e2e_dash_demo.png", full_page=True)
        await dp.emulate_media(color_scheme="dark")
        await dp.screenshot(path=f"{SHOTS}/e2e_dash_demo_dark.png", full_page=False)
        mob = await browser.new_context(viewport={"width": 390, "height": 844}, storage_state=await demo.storage_state())
        mp = await mob.new_page(); await mp.goto(f"{BASE}/dashboard")
        await expect(mp.get_by_text("Demo data")).to_be_visible()
        await mp.screenshot(path=f"{SHOTS}/e2e_dash_mobile.png", full_page=False)
        await demo.close(); await mob.close()

        check("no uncaught page errors", not errors, "; ".join(errors[:3]))
        await browser.close()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)

asyncio.run(main())
