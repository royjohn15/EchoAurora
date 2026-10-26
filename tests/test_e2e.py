"""End-to-end check: a fake microphone plays synthetic claps (known RT60) into the app at a phone viewport,
with simulated motion. Measures three seats, then screenshots every tab.
Run:  python3 tests/test_e2e.py out_dir [rt60_seconds]
Serves the app on http://localhost:8766 (localhost counts as a secure context).
"""
import http.server, pathlib, sys, threading, functools, json, time, wave
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
T = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8

# 12 s loop: room noise, a clap at 4 s and another at 10 s
sr, rng = 48000, np.random.default_rng(1)
x = 0.0008 * rng.standard_normal(12 * sr)
for at in (4, 10):
    t = np.arange(int(3.0 * sr)) / sr
    burst = 0.45 * rng.standard_normal(t.size) * np.exp(-6.9078 * t / T)
    burst[:96] += 0.5 * rng.standard_normal(96)  # the sharp hand-slap
    x[at * sr: at * sr + t.size] += burst[: min(t.size, x.size - at * sr)]
wav = out / f"claps_T{T}.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()

MOTION = r"""
(mode) => {
  clearInterval(window.__mot); let i = 0;
  window.__mot = setInterval(() => {
    i++; const j = mode === 'moving' ? 0.8 : 0.01;
    window.dispatchEvent(new DeviceMotionEvent('devicemotion', {
      acceleration: {x: j * Math.sin(i * 2.1), y: j * Math.cos(i * 1.7), z: 0.01 * Math.sin(i)},
      accelerationIncludingGravity: {x: 0, y: 0, z: 9.81},
      rotationRate: {alpha: mode === 'moving' ? 40 : 0.3, beta: 0.2, gamma: 0.1}, interval: 16}));
  }, 1000 / 60);
}
"""

def measure_seat(pg, fx, fy):
    box = pg.locator("#miniMap").bounding_box()
    pg.mouse.click(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
    pg.evaluate("window.__prev = S.last")
    pg.click("#listenBtn")
    pg.wait_for_function("S.state==='idle' && S.last && S.last !== window.__prev", timeout=30000)
    return pg.evaluate("({ok:S.last.ok, rt:S.last.rt, c50:S.last.c50, reason:S.last.reason, motion:S.last.motion.status})")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                f"--use-file-for-fake-audio-capture={wav}", "--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                        permissions=["microphone"])
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.goto("http://localhost:8766/index.html")
    pg.evaluate("localStorage.clear()"); pg.reload()
    pg.screenshot(path=str(out / "0_start.png"))
    pg.click("#startBtn")
    pg.evaluate(MOTION, "still")
    time.sleep(1.5)
    pg.screenshot(path=str(out / "1_ready.png"))
    results = []
    for fx, fy in [(0.5, 0.35), (0.25, 0.65), (0.75, 0.9), (0.5, 0.35)]:
        results.append(measure_seat(pg, fx, fy))
    time.sleep(0.5)
    pg.screenshot(path=str(out / "2_measured.png"), full_page=True)
    # moving phone must be rejected
    pg.evaluate(MOTION, "moving")
    results.append(measure_seat(pg, 0.5, 0.35))
    pg.evaluate(MOTION, "still")
    pg.screenshot(path=str(out / "2b_rejected.png"))
    pg.click("nav button[data-tab=room]"); time.sleep(1.5); pg.screenshot(path=str(out / "3_room.png"), full_page=True)
    pg.click("nav button[data-tab=fix]"); time.sleep(0.8); pg.screenshot(path=str(out / "4_fix.png"), full_page=True)
    pg.click("nav button[data-tab=method]"); time.sleep(0.5); pg.screenshot(path=str(out / "5_method.png"), full_page=True)
    seats = pg.evaluate("S.seats.map(s=>({id:s.id, n:s.claps.length, ...seatStats(s)}))")
    b.close()
srv.shutdown()
for r in results: print(r)
for s in seats: print(s)
print("ERRORS:", errors or "none")
