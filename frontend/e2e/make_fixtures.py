"""Create the small files e2e/phase2.py uploads (needs Pillow; ffmpeg for the video clip)."""
import os, shutil, subprocess, sys
from PIL import Image

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/e2e"
os.makedirs(out, exist_ok=True)
Image.new("RGB", (900, 700), (20, 110, 100)).save(f"{out}/teal.png")
Image.new("RGB", (800, 800), (230, 190, 80)).save(f"{out}/bun.jpg", quality=85)
open(f"{out}/fake.png", "wb").write(b"<html>not an image</html>")  # must be rejected
ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    sys.exit("ffmpeg not found: install it to create clip.mp4")
subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24",
                "-t", "2", "-pix_fmt", "yuv420p", f"{out}/clip.mp4"], check=True)
print(f"fixtures written to {out}")
