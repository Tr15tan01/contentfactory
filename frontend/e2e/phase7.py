"""Phase 7 browser checks: generate an image (development placeholder provider), reuse at no
charge, build a video from own media with ffmpeg, and generate straight into a post.

Run against a running stack with the worker:  python3 e2e/make_fixtures.py && python3 e2e/phase7.py
"""
import asyncio, os, re, sys, time, uuid
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
FIX = os.environ.get("FIXTURES", "/tmp/e2e")
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

async def api(page, path, method="GET", body=None):
    return await page.evaluate("""async ([p, m, b]) => {
      const csrf = decodeURIComponent((document.cookie.split('; ').find(c => c.startsWith('cf_csrf=')) || '=').split('=')[1]);
      const r = await fetch('/api/v1' + p, {method: m, headers: {'content-type': 'application/json', 'x-csrf-token': csrf}, body: b ? JSON.stringify(b) : undefined});
      return r.status === 204 ? null : r.json(); }""", [path, method, body])

async def main():
    email = f"p7-{RUN}@example.com"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(bypass_csp=True, viewport={"width": 1440, "height": 1000})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{BASE}/register")
        await page.fill("#full_name", "Salome Gelashvili"); await page.fill("#email", email); await page.fill("#password", "reels-from-my-photos")
        await page.click("button[type=submit]"); await expect(page.get_by_text("Check your inbox")).to_be_visible()
        await page.goto(f"{BASE}/verify-email?token={token_for(email)}"); await page.wait_for_url("**/onboarding")
        ws = (await api(page, "/workspaces"))[0]["id"]

        await page.goto(f"{BASE}/media")
        await page.set_input_files("input[type=file]", [f"{FIX}/bun.jpg", f"{FIX}/clip.mp4"])
        await expect(page.get_by_text("2 files")).to_be_visible(timeout=20000)
        await page.wait_for_function("[...document.querySelectorAll('main img')].filter(i => i.complete && i.naturalWidth > 0).length >= 2", timeout=30000)

        # Generate an image
        await page.get_by_role("button", name="Generate image").click()
        dialog = page.get_by_role("dialog")
        await expect(dialog.get_by_text("Development mode")).to_be_visible()
        check("development placeholder is disclosed before generating", True)
        await page.fill("#img-prompt", f"A cardamom bun on a wooden counter {RUN}")
        await dialog.get_by_role("button", name="Generate", exact=True).click()
        await expect(page.get_by_text("Generating your image")).to_be_visible()
        await expect(page.get_by_text("Placeholder", exact=True)).to_be_visible(timeout=30000)
        check("generated image lands in the library, labelled as a placeholder in development", True)
        usage = await api(page, f"/workspaces/{ws}/usage")
        check("one image counted", usage["images"]["used"] == 1, str(usage["images"]))

        await page.get_by_role("button", name="Generate image").click()
        await page.fill("#img-prompt", f"A cardamom bun on a wooden counter {RUN}")
        await page.get_by_role("dialog").get_by_role("button", name="Generate", exact=True).click()
        await expect(page.get_by_text("we reused it. Nothing was charged")).to_be_visible()
        check("identical request is reused, not charged", (await api(page, f"/workspaces/{ws}/usage"))["images"]["used"] == 1)

        # Build a video from the photo and the clip
        await page.get_by_role("button", name="Build video").click()
        dialog = page.get_by_role("dialog").first
        await dialog.get_by_role("button", name="Choose media for scene 1").click()
        picker = page.get_by_role("dialog", name="Choose a photo or clip")
        await picker.get_by_role("button", name="bun", exact=True).click()
        await picker.get_by_role("button", name=re.compile("^Use 1")).click()
        await dialog.get_by_label("Scene 1 text").fill("Fresh today")
        await dialog.get_by_role("button", name="Add scene").click()
        await dialog.get_by_role("button", name="Choose media for scene 2").click()
        picker = page.get_by_role("dialog", name="Choose a photo or clip")
        await picker.get_by_role("button", name="clip", exact=True).click()
        await picker.get_by_role("button", name=re.compile("^Use 1")).click()
        await expect(dialog.get_by_text("6.0 s, 1 video credit")).to_be_visible()
        check("builder shows length and credit cost", True)
        await dialog.get_by_role("button", name="Build video").click()
        await expect(page.get_by_text("Building your video")).to_be_visible()
        await expect(page.get_by_text("Built video")).to_be_visible(timeout=60000)
        items = (await api(page, f"/workspaces/{ws}/media?kind=video"))["items"]
        built = next(i for i in items if i["source"] == "assembled")
        check("video built: vertical 1080x1920, about 6 seconds", (built["width"], built["height"]) == (1080, 1920) and 5.7 <= built["duration_seconds"] <= 6.4, str((built["width"], built["height"], built["duration_seconds"])))
        check("one video credit counted", (await api(page, f"/workspaces/{ws}/usage"))["video_credits"]["used"] == 1)
        await page.screenshot(path=f"{SHOTS}/p7_media.png")

        # Generate straight into a post
        post = await api(page, f"/workspaces/{ws}/content", "POST", {"title": "Weekend special", "platforms": ["instagram"], "caption": "Cardamom buns all weekend."})
        await page.goto(f"{BASE}/content/{post['id']}")
        await page.get_by_role("button", name="Generate image").click()
        await page.fill("#img-prompt", f"A tray of cardamom buns {RUN}")
        await page.get_by_role("dialog").get_by_role("button", name="Generate", exact=True).click()
        await expect(page.get_by_text("The image is added to this post")).to_be_visible()
        for _ in range(30):
            detail = await api(page, f"/workspaces/{ws}/content/{post['id']}")
            if detail["media"]:
                break
            await asyncio.sleep(1)
        check("generated image attached to the post", len(detail["media"]) == 1, str(detail["media"]))

        check("no uncaught page errors", not errors, "; ".join(errors[:3]))
        await browser.close()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)

asyncio.run(main())
