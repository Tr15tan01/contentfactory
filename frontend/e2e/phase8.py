"""Phase 8 browser checks: approval reminder in the notification bell, notification settings,
agent activity timeline, admin area with suspension, and the Content-Security-Policy.

Run against a running stack with the worker:  python3 e2e/phase8.py
"""
import asyncio, os, re, subprocess, sys, time, uuid
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
BACKEND = os.environ.get("BACKEND_DIR", "../backend")
WORKER_LOG = os.environ.get("WORKER_LOG", "/tmp/worker.log")
SHOTS = os.environ.get("SHOTS", "/tmp")
RUN = uuid.uuid4().hex[:6]
results = []

def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))

def token_for(email, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        m = re.findall(rf"--- email to {re.escape(email)} ---.*?/verify-email\?token=([A-Za-z0-9_\-]+)", open(WORKER_LOG).read(), re.S)
        if m: return m[-1]
        time.sleep(0.5)

def sql(q):
    subprocess.run(["psql", "-h", "localhost", "-U", "cf", "contentfactory", "-c", q], env={**os.environ, "PGPASSWORD": "cf"}, check=True, capture_output=True)

def run_reminders():
    code = "import asyncio\nfrom app.core.database import SessionLocal\nfrom app.notifications.reminders import send_reminders\nasync def m():\n    async with SessionLocal() as db:\n        print(await send_reminders(db))\nasyncio.run(m())"
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, check=True, capture_output=True, text=True).stdout.strip()

async def api(page, path, method="GET", body=None):
    return await page.evaluate("""async ([p, m, b]) => {
      const csrf = decodeURIComponent((document.cookie.split('; ').find(c => c.startsWith('cf_csrf=')) || '=').split('=')[1]);
      const r = await fetch('/api/v1' + p, {method: m, headers: {'content-type': 'application/json', 'x-csrf-token': csrf}, body: b ? JSON.stringify(b) : undefined});
      return {status: r.status, body: r.status === 204 ? null : await r.json()}; }""", [path, method, body])

async def register(ctx, email, name):
    page = await ctx.new_page()
    await page.goto(f"{BASE}/register")
    await page.fill("#full_name", name); await page.fill("#email", email); await page.fill("#password", "operations-check-8")
    await page.click("button[type=submit]"); await expect(page.get_by_text("Check your inbox")).to_be_visible()
    await page.goto(f"{BASE}/verify-email?token={token_for(email)}"); await page.wait_for_url("**/onboarding")
    return page

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        owner_ctx = await browser.new_context(viewport={"width": 1440, "height": 1000})
        page = await register(owner_ctx, f"p8-owner-{RUN}@example.com", "Tamar Owner")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Content Security Policy" in m.text else None)
        ws = (await api(page, "/workspaces"))["body"][0]["id"]

        # A post due in 3 hours that nobody approved -> reminder
        post = (await api(page, f"/workspaces/{ws}/content", "POST", {"title": f"Harvest festival {RUN}", "platforms": ["instagram"], "caption": "x"}))["body"]
        from datetime import UTC, datetime, timedelta
        await api(page, f"/workspaces/{ws}/content/{post['id']}/schedule", "PUT", {"scheduled_at": (datetime.now(UTC) + timedelta(hours=3)).isoformat()})
        check("reminder job creates one reminder", run_reminders() == "1")
        await page.goto(f"{BASE}/dashboard")
        bell = page.get_by_role("button", name=re.compile(r"Notifications, 1 unread"))
        await expect(bell).to_be_visible()
        await bell.click()
        await page.get_by_role("menuitem", name=re.compile(f"Approve .Harvest festival {RUN}")).click()
        await page.wait_for_url(f"**/content/{post['id']}")
        await expect(page.get_by_role("button", name="Notifications", exact=True)).to_be_visible()
        check("bell shows the reminder, opens the post, and clears it", True)

        await page.goto(f"{BASE}/settings/notifications")
        row = page.get_by_role("row", name=re.compile("Posts waiting for approval"))
        await row.get_by_label("Posts waiting for approval by email").uncheck()
        await page.get_by_role("button", name="Save").click()
        await expect(page.get_by_text("Saved", exact=True)).to_be_visible()
        prefs = (await api(page, f"/workspaces/{ws}/notification-preferences"))["body"]
        check("email preference saved", next(p for p in prefs if p["type"] == "pre_publish_reminder")["email"] is False)

        # Agent activity: an AI draft leaves a run with steps
        r = await api(page, f"/workspaces/{ws}/content/generate", "POST", {"idea": "Why our bread is sourdough", "platforms": ["instagram"]})
        for _ in range(20):
            if (await api(page, f"/workspaces/{ws}/content/{r['body']['id']}"))["body"]["status"] != "generating":
                break
            await asyncio.sleep(1)
        await page.goto(f"{BASE}/agent")
        await page.get_by_role("button", name=re.compile("Content agent")).first.click()
        await expect(page.get_by_text("Read the business profile and brand voice")).to_be_visible()
        check("agent activity shows the draft run with its steps", await page.get_by_text("of 20 steps", exact=False).count() == 1)
        await page.screenshot(path=f"{SHOTS}/p8_agent.png")

        # Admin: a customer gets suspended and loses their session immediately
        cust_ctx = await browser.new_context()
        customer = await register(cust_ctx, f"p8-customer-{RUN}@example.com", "Customer Eight")
        check("no admin area for normal users", await page.get_by_role("link", name="Admin").count() == 0)
        sql(f"update users set is_superuser = true where email = 'p8-owner-{RUN}@example.com'")
        await page.goto(f"{BASE}/admin")
        await expect(page.get_by_role("heading", name="Customers")).to_be_visible()
        await page.fill("input[placeholder='Email or name']", f"p8-customer-{RUN}")
        row = page.get_by_role("row", name=re.compile(f"p8-customer-{RUN}"))
        await expect(row).to_be_visible()
        page.once("dialog", lambda d: asyncio.ensure_future(d.accept("Chargeback fraud")))
        await row.get_by_role("button", name="Suspend").click()
        await expect(row.get_by_text("suspended")).to_be_visible()
        check("admin suspends a customer", True)
        check("suspended customer's session ends at once", (await api(customer, "/auth/me"))["status"] == 401)
        await expect(page.get_by_text("admin.user_suspended").first).to_be_visible()
        check("suspension is in the audit log", True)
        await page.screenshot(path=f"{SHOTS}/p8_admin.png", full_page=True)

        csp = (await page.request.get(f"{BASE}/")).headers.get("content-security-policy", "")
        check("pages send a Content-Security-Policy", "default-src 'self'" in csp and "frame-ancestors 'none'" in csp)
        check("no page errors or CSP violations", not errors, "; ".join(errors[:3]))
        await browser.close()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)

asyncio.run(main())
