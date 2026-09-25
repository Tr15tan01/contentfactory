"""Phase 4 browser checks: billing page driven by signed Paddle webhooks.

Needs the API started with test Paddle settings and PADDLE_API_BASE_URL pointing at the
stand-in this script runs on :8099 (see docs/billing.md, "Testing billing locally").
The script plays Paddle's part by sending signed webhooks; it never fakes state in the app.
"""
import asyncio, hashlib, hmac, json, os, re, sys, threading, time, uuid
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
import httpx
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
API = os.environ.get("API_URL", "http://127.0.0.1:8000/api/v1")
SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_e2e")
PRICES = {"starter": "pri_e2e_starter", "business": "pri_e2e_business", "agency": "pri_e2e_agency"}
WORKER_LOG = os.environ.get("WORKER_LOG", "/tmp/worker.log")
SHOTS = os.environ.get("SHOTS", "/tmp")
calls: list[tuple[str, str, dict]] = []
SUB = f"sub_e2e_{uuid.uuid4().hex[:10]}"  # Paddle subscription ids are unique; so are ours per run
results = []

class PaddleStandIn(BaseHTTPRequestHandler):
    def _reply(self):
        n = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        calls.append((self.command, self.path, body))
        data = {"urls": {"general": {"overview": "https://customer-portal.example/cpl_e2e"}}} if self.path.endswith("portal-sessions") else {"id": SUB}
        out = json.dumps({"data": data}).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)
    do_PATCH = do_POST = _reply
    def log_message(self, *a): pass

def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))

def token_for(email, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        m = re.findall(rf"--- email to {re.escape(email)} ---.*?/verify-email\?token=([A-Za-z0-9_\-]+)", open(WORKER_LOG).read(), re.S)
        if m: return m[-1]
        time.sleep(0.5)

def webhook(custom, plan, *, status="active", scheduled=None, kind="subscription.updated"):
    start = datetime.now(UTC) - timedelta(days=1)
    body = json.dumps({
        "event_id": f"evt_{uuid.uuid4().hex}", "event_type": kind, "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "data": {"id": SUB, "status": status, "customer_id": "ctm_e2e", "custom_data": custom, "scheduled_change": scheduled,
                 "items": [{"price": {"id": PRICES[plan], "product_id": "pro_e2e", "billing_cycle": {"interval": "month", "frequency": 1},
                                      "unit_price": {"amount": {"starter": "1900", "business": "4900", "agency": "9900"}[plan], "currency_code": "USD"}}, "quantity": 1}],
                 "current_billing_period": {"starts_at": start.isoformat(), "ends_at": (start + timedelta(days=30)).isoformat()}},
    }).encode()
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    r = httpx.post(f"{API}/billing/webhooks/paddle", content=body, headers={"paddle-signature": f"ts={ts};h1={sig}", "content-type": "application/json"})
    return r.json()["status"]

async def main():
    server = HTTPServer(("127.0.0.1", 8099), PaddleStandIn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    email = f"p4-{uuid.uuid4().hex[:8]}@example.com"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(viewport={"width": 1440, "height": 1000})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{BASE}/register")
        await page.fill("#full_name", "Mariam Lomidze"); await page.fill("#email", email); await page.fill("#password", "paddle-pays-the-bills")
        await page.click("button[type=submit]"); await expect(page.get_by_text("Check your inbox")).to_be_visible()
        await page.goto(f"{BASE}/verify-email?token={token_for(email)}"); await page.wait_for_url("**/onboarding")

        await page.goto(f"{BASE}/settings/billing")
        await expect(page.get_by_text("AI drafts", exact=True)).to_be_visible()
        check("free plan shown with usage meters", await page.get_by_text("Current plan").count() == 1)
        choose = page.get_by_role("button", name="Choose Business")
        check("checkout available when Paddle is configured", await choose.is_enabled())

        # The checkout params the page would hand to Paddle.js (signed custom_data included)
        params = await page.evaluate("""async () => {
          const csrf = decodeURIComponent(document.cookie.split('; ').find(c => c.startsWith('cf_csrf=')).split('=')[1]);
          const r = await fetch('/api/v1/billing/checkout', {method: 'POST', headers: {'content-type': 'application/json', 'x-csrf-token': csrf}, body: JSON.stringify({plan: 'starter'})});
          return r.json(); }""")
        check("checkout params carry a signed user reference", params["price_id"] == PRICES["starter"] and len(params["custom_data"]["sig"]) == 40)

        # Paddle confirms the purchase
        check("signed subscription.created webhook applied", webhook(params["custom_data"], "starter", kind="subscription.created") == "applied")
        await page.reload()
        await expect(page.get_by_text("Renews on")).to_be_visible()
        check("page shows Starter after Paddle's webhook", await page.locator("p.display").inner_text() == "Starter")

        # Upgrade: the app asks Paddle, then waits for the webhook
        await page.get_by_role("button", name="Upgrade to Business").click()
        await page.get_by_role("dialog").get_by_role("button", name="Upgrade").click()
        await expect(page.get_by_text("Confirming with Paddle")).to_be_visible()
        check("upgrade sent to Paddle as a prorated price change", calls and calls[-1][0] == "PATCH" and calls[-1][2]["items"][0]["price_id"] == PRICES["business"] and calls[-1][2]["proration_billing_mode"] == "prorated_immediately", str(calls[-1:] ))
        check("plan unchanged before Paddle confirms", await page.locator("p.display").inner_text() == "Starter")
        webhook(params["custom_data"], "business")
        await expect(page.get_by_text("Confirming with Paddle")).to_be_hidden(timeout=10000)
        await expect(page.locator("p.display")).to_have_text("Business")
        check("page updates by itself once Paddle confirms", True)
        await expect(page.get_by_text("of 250", exact=False).or_(page.get_by_text("/ 250"))).to_be_visible()
        check("limits follow the new plan", True)
        await page.screenshot(path=f"{SHOTS}/p4_billing.png", full_page=True)

        # Cancel at period end, then keep it
        await page.get_by_role("button", name="Cancel subscription").click()
        await page.get_by_role("dialog").get_by_role("button", name="Cancel at period end").click()
        await page.wait_for_timeout(500)
        check("cancel requested at next billing period", calls[-1][1] == f"/subscriptions/{SUB}/cancel" and calls[-1][2] == {"effective_from": "next_billing_period"}, str(calls[-1:]))
        webhook(params["custom_data"], "business", scheduled={"action": "cancel", "effective_at": (datetime.now(UTC) + timedelta(days=29)).isoformat()})
        await expect(page.get_by_role("button", name="Keep my subscription")).to_be_visible(timeout=10000)
        check("scheduled cancellation shown with an undo", await page.get_by_text("Ends on").count() == 1)

        await page.context.route("https://customer-portal.example/**", lambda route: route.fulfill(status=200, body="portal"))
        async with page.expect_popup() as pop:
            await page.get_by_role("button", name=re.compile("Invoices and payment method")).click()
        popup = await pop.value
        check("customer portal opens in a new tab", popup.url.startswith("https://customer-portal.example/"), popup.url)

        check("no uncaught page errors", not errors, "; ".join(errors[:3]))
        await browser.close()
    server.shutdown()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)

asyncio.run(main())
