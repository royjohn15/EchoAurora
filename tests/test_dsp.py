"""Unit tests for Echo Aurora's acoustics maths, executed inside headless Chromium against the app's own functions.
Synthetic claps: white noise decaying exponentially with a known RT60, over a steady background noise.
Run:  python3 tests/test_dsp.py
"""
import pathlib, sys
from playwright.sync_api import sync_playwright

APP = pathlib.Path(__file__).resolve().parent.parent / "index.html"

JS = r"""
() => {
  const out = [];
  const ok = (name, got, want, tol) => out.push({name, got, want, pass: Math.abs(got - want) <= tol});
  const is = (name, got, want) => out.push({name, got, want, pass: got === want});
  // seeded noise so the tests are repeatable
  let seed = 12345; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const gauss = () => Math.sqrt(-2 * Math.log(rnd() + 1e-12)) * Math.cos(2 * Math.PI * rnd());
  // pre seconds of background, then a decay with RT60 = T, peak-to-noise ratio snr dB
  function clap(sr, T, snr, opts = {}) {
    const pre = Math.round(PRE_S * sr), n = pre + Math.round(POST_S * sr), x = new Float32Array(n);
    const amp = 0.5, noise = amp * Math.pow(10, -snr / 20);
    for (let i = 0; i < n; i++) {
      let v = noise * gauss();
      if (i >= pre) { const t = (i - pre) / sr; v += amp * gauss() * Math.exp(-6.9078 * t / T); }
      if (opts.second && i >= pre + Math.round(opts.second * sr) && i < pre + Math.round((opts.second + 0.03) * sr)) v += 0.4 * gauss();
      x[i] = v;
    }
    return {x, trig: pre};
  }
  const sr = 48000;
  // 1) RT60 recovered for short, classroom and echoey rooms (within 5 %)
  for (const T of [0.4, 0.8, 1.6]) {
    const {x, trig} = clap(sr, T, 55);
    const r = analyzeClap(x, sr, trig);
    ok(`RT60 (mid) for T = ${T} s`, r.rt, T, 0.05 * T);
    for (const b of r.bands.filter(b => MID.includes(b.fc))) ok(`  T20 ${b.fc} Hz for T = ${T} s`, b.T20 ? b.T20.T : NaN, T, 0.07 * T);
    // 2) C50 of an exponential decay: 10 log10(e^{0.05k} - 1), k = 13.8155 / T
    const k = 6 * Math.LN10 / T, want = 10 * Math.log10(Math.exp(0.05 * k) - 1);
    ok(`C50 formula, full-range signal, T = ${T} s (analytic ${want.toFixed(2)} dB)`, bandDecay(Float64Array.from(x), sr, trig, trig - 960).C50, want, 0.3);
    // a single noise burst has ~1 dB of natural scatter per band, so check for bias over 12 different claps
    let acc = 0; for (let s = 0; s < 12; s++) { const c = clap(sr, T, 55); acc += analyzeClap(c.x, sr, c.trig).c50; }
    ok(`C50 speech bands, mean of 12 claps, T = ${T} s`, acc / 12, want, 0.5);
    is(`clap accepted for T = ${T} s`, r.ok, true);
  }
  // 3) 44.1 kHz phones
  { const {x, trig} = clap(44100, 0.7, 50); ok("RT60 at 44.1 kHz, T = 0.7 s", analyzeClap(x, 44100, trig).rt, 0.7, 0.035); }
  // 4) tail correction matters: moderate SNR still gives the right answer
  { const {x, trig} = clap(sr, 1.0, 40); const r = analyzeClap(x, sr, trig); ok("RT60 with only 40 dB SNR, T = 1.0 s", r.rt, 1.0, 0.07); }
  // 5) quality gates
  { const {x, trig} = clap(sr, 0.8, 22); const r = analyzeClap(x, sr, trig); is("22 dB SNR clap rejected as too quiet", r.ok, false); }
  { const {x, trig} = clap(sr, 0.8, 55, {second: 0.5}); const r = analyzeClap(x, sr, trig); is("second sound during decay rejected", r.second, true); is("  ...and clap not accepted", r.ok, false); }
  { const {x, trig} = clap(sr, 0.8, 32); const r = analyzeClap(x, sr, trig);
    out.push({name: "32 dB SNR graded fair, not good", got: r.bands.find(b => b.fc === 1000).grade.q, want: "fair", pass: r.bands.find(b => b.fc === 1000).grade.q === "fair"}); }
  // 6) ANSI S12.60 targets and Sabine maths
  ok("target for 150 m3 classroom", ansiTarget(150), 0.6, 0);
  ok("target for 400 m3 classroom", ansiTarget(400), 0.7, 0);
  is("no ANSI target above 566 m3", ansiTarget(800), null);
  { const f = sabineFix(144, 1.2, 0.6); ok("Sabine dA for V=144, 1.2 -> 0.6 s", f.dA, 0.161 * 144 * (1 / 0.6 - 1 / 1.2), 1e-9);
    ok("  panel area = dA / (0.9 - 0.03)", f.items[0].area, f.dA / 0.87, 1e-9);
    // check the round trip: adding that absorption to A_now gives exactly the target
    const Anow = 0.161 * 144 / 1.2; ok("  round trip RT after fix", 0.161 * 144 / (Anow + f.dA), 0.6, 1e-9); }
  is("no treatment when already under target", sabineFix(144, 0.5, 0.6).items[0].area, 0);
  ok("median of [3,1,2,10]", median([3, 1, 2, 10]), 2.5, 1e-12);
  return out;
}
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(APP.as_uri())
    res = pg.evaluate(JS)
    b.close()

fails = 0
for r in res:
    got = r["got"]
    got = f"{got:.4f}" if isinstance(got, float) else got
    print(("PASS " if r["pass"] else "FAIL ") + f'{r["name"]}: got {got}, want {r["want"]}')
    fails += not r["pass"]
print(f"\n{len(res) - fails}/{len(res)} passed")
sys.exit(1 if fails else 0)
