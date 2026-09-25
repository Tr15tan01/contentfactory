"""Phase 5 browser checks: connect Meta accounts through OAuth, publish a scheduled post.

The API must run with META_CLIENT_ID/SECRET set and META_DIALOG_BASE_URL and
META_GRAPH_BASE_URL pointing at the stand-in this script serves on :8098
(see docs/social-publishing.md, "Testing locally"). The stand-in plays Meta: its login
dialog redirects straight back with a code, and its Graph API returns ids.
"""
import asyncio, json, os, re, subprocess, sys, threading, time, uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
FIX = os.environ.get("FIXTURES", "/tmp/e2e")
WORKER_LOG = os.environ.get("WORKER_LOG", "/tmp/worker.log")
SHOTS = os.environ.get("SHOTS", "/tmp")
RUN = uuid.uuid4().hex[:6]
calls = []
results = []

class MetaStandIn(BaseHTTPRequestHandler):
    def _json(self, body, status=200):
        out = json.dumps(body).encode()
        self.send_response(status); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def do_GET(self):
        url = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(url.query).items()}
        calls.append(("GET", url.path, q))
        if url.path.endswith("/dialog/oauth"):  # the "login": straight back with a code
            self.send_response(302); self.send_header("location", f"{q['redirect_uri']}?{urlencode({'code': 'e2e-code', 'state': q['state']})}"); self.end_headers(); return
        if url.path.endswith("/oauth/access_token"): return self._json({"access_token": "LONG" if "fb_exchange_token" in q else "SHORT"})
        if url.path.endswith("/me/accounts"):
            return self._json({"data": [{"id": f"page_{RUN}", "name": "Vake Roasters", "access_token": "PAGE-TOKEN",
                                         "instagram_business_account": {"id": f"ig_{RUN}", "username": "vakeroasters"}}]})
        if "/container" in url.path: return self._json({"status_code": "FINISHED"})
        if url.path.endswith(f"/igmedia_{RUN}"): return self._json({"permalink": f"https://www.instagram.com/p/{RUN}/"})
        return self._json({"error": {"code": 803, "message": "unknown"}}, 404)
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0); body = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
        path = urlparse(self.path).path; calls.append(("POST", path, body))
        if path.endswith("/media"): return self._json({"id": f"container_{RUN}"})
        if path.endswith("/media_publish"): return self._json({"id": f"igmedia_{RUN}"})
        return self._json({"error": {"code": 803}}, 404)
    def log_message(self, *a): pass

def check(name, ok, detail=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))

def token_for(email, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        m = re.findall(rf"--- email to {re.escape(email)} ---.*?/verify-email\?token=([A-Za-z0-9_\-]+)", open(WORKER_LOG).read(), re.S)
        if m: return m[-1]
        time.sleep(0.5)

async def main():
    server = HTTPServer(("127.0.0.1", 8098), MetaStandIn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    email = f"p5-{RUN}@example.com"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(bypass_csp=True, viewport={"width": 1440, "height": 1000})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{BASE}/register")
        await page.fill("#full_name", "Giorgi Tsereteli"); await page.fill("#email", email); await page.fill("#password", "publish-it-at-six")
        await page.click("button[type=submit]"); await expect(page.get_by_text("Check your inbox")).to_be_visible()
        await page.goto(f"{BASE}/verify-email?token={token_for(email)}"); await page.wait_for_url("**/onboarding")
        subprocess.run([sys.executable, "-m", "scripts.set_plan", email, "starter", "--by", "e2e"], cwd=os.environ.get("BACKEND_DIR", "../backend"), check=True, capture_output=True)

        await page.goto(f"{BASE}/settings/social")
        await expect(page.get_by_text("Connected accounts")).to_be_visible()
        check("unconfigured providers say so", await page.get_by_text("Not available on this server yet").count() == 2)
        await page.get_by_role("button", name="Connect Instagram and Facebook").click()
        await page.wait_for_url(re.compile(r"/settings/social\?connected=2"))
        await expect(page.get_by_text("2 accounts connected")).to_be_visible()
        check("OAuth round trip connects the Page and its Instagram account", await page.get_by_text("@vakeroasters").count() == 1)
        await page.screenshot(path=f"{SHOTS}/p5_social.png")

        # A post with a JPEG, approved and scheduled a little ahead
        await page.goto(f"{BASE}/media")
        await page.set_input_files("input[type=file]", f"{FIX}/bun.jpg")
        await page.wait_for_function("[...document.querySelectorAll('main img')].some(i => i.complete && i.naturalWidth > 0)", timeout=20000)
        media = await page.evaluate("async () => (await (await fetch('/api/v1/workspaces')).json())[0].id")
        ws = media
        media_id = await page.evaluate(f"async () => (await (await fetch('/api/v1/workspaces/{ws}/media')).json()).items[0].id")
        post_id = await page.evaluate("""async ([ws, mid]) => {
          const csrf = decodeURIComponent(document.cookie.split('; ').find(c => c.startsWith('cf_csrf=')).split('=')[1]);
          const h = {'content-type': 'application/json', 'x-csrf-token': csrf};
          const c = await (await fetch(`/api/v1/workspaces/${ws}/content`, {method: 'POST', headers: h, body: JSON.stringify({title: 'Tuesday roast', platforms: ['instagram'], caption: 'Fresh beans today.', hashtags: ['VakeRoasters'], media_ids: [mid]})})).json();
          await fetch(`/api/v1/workspaces/${ws}/content/${c.id}/approve`, {method: 'POST', headers: h});
          const when = new Date(Date.now() + 6 * 60 * 1000).toISOString();
          await fetch(`/api/v1/workspaces/${ws}/content/${c.id}/schedule`, {method: 'PUT', headers: h, body: JSON.stringify({scheduled_at: when})});
          return c.id; }""", [ws, media_id])
        await page.goto(f"{BASE}/content/{post_id}")
        await expect(page.get_by_text("Publishes automatically on")).to_be_visible()
        check("editor confirms automatic publishing", True)

        # Time passes: move the schedule into the past, then the worker's minute cron publishes it
        subprocess.run(["psql", "-h", "localhost", "-U", "cf", "contentfactory", "-c",
                        f"update content_schedules set scheduled_at = now() - interval '5 seconds' where content_id = '{post_id}'"],
                       env={**os.environ, "PGPASSWORD": "cf"}, check=True, capture_output=True)
        await page.reload()  # the page now sees a post that's due, and watches it go out
        await expect(page.get_by_role("link", name="View post")).to_be_visible(timeout=90000)
        check("worker published it and the editor shows the link", True)
        link = await page.get_by_role("link", name="View post").get_attribute("href")
        check("link is the platform's permalink", link == f"https://www.instagram.com/p/{RUN}/", link)
        container = next(b for m, path, b in calls if m == "POST" and path.endswith("/media"))
        check("Meta received an absolute media URL and the hashtags", container["image_url"].startswith("http") and "#VakeRoasters" in container["caption"])
        check("published exactly once", sum(1 for m, path, _ in calls if m == "POST" and path.endswith("/media_publish")) == 1)
        await page.screenshot(path=f"{SHOTS}/p5_published.png")
        check("published post is locked (no schedule, read-only caption)", await page.get_by_role("button", name="Schedule").count() == 0 and await page.locator("#caption").is_disabled())
        await page.goto(f"{BASE}/content")
        row = page.locator(f"a[href='/content/{post_id}']")
        await expect(row).to_be_visible()
        check("content list shows Published", "Published" in await row.inner_text(), await row.inner_text())

        check("no uncaught page errors", not errors, "; ".join(errors[:3]))
        await browser.close()
    server.shutdown()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)

asyncio.run(main())
