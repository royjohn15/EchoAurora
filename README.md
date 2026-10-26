# Echo Aurora: can every seat understand the speaker?

A phone web app that measures a room's **reverberation time (RT60)** and **speech clarity (C50)** from a single
hand clap, maps clarity **seat by seat** as glowing aurora on a room plan, and tells you **how many square metres
of panels, curtains or carpet** would bring the room to the classroom standard.

**The decision it supports:** *Is this room too echoey for teaching or meetings, which seats suffer, and what do I
add to fix it?*

## Sensors used

| Sensor | What it is used for |
|---|---|
| Microphone | Captures the clap and its echo (raw audio, with echo cancellation, noise suppression and auto-gain switched off). Gives RT60 and C50 in five octave bands, plus the live aurora spectrogram. |
| Accelerometer | Rejects claps where the phone was jolted as the sound started (a knock on the desk, not a clap in the air), and claps where the phone moved. |
| Gyroscope | Rejects claps where the phone rotated during the 3-second recording. |
| Vibration motor | Buzzes once the echo has been captured, so you know it's safe to move. |

## How to use it

1. On the **Room** tab, enter the room's length, width and height.
2. On **Measure**, tap the plan where the phone is sitting, and put the phone flat on that seat.
3. Tap **Listen**, walk to the front of the room (where a teacher would stand) and clap once, sharply.
4. Clap twice per seat, then repeat at 3 or more seats: front, middle, back corner.
5. **Room** shows the clarity map. **Fix** shows how much absorption the room needs.

## Visualizations

- **Live aurora:** a scrolling spectrogram of the room (100 Hz to 8 kHz, log scale). A clap shows up as a bright curtain that fades.
- **The clap, fading away:** a spectrogram of the captured echo, with RT60 marked.
- **Decay curve:** the Schroeder energy-decay curve per band, the −5 to −25 dB fit range, and the fitted line extended to −60 dB. Tap it to read values.
- **RT60 by pitch:** T20 per octave band against the target line. Hollow dots are bands with a weaker signal; crosses are bands too quiet to measure.
- **Clarity across the room:** each measured seat glows on the room plan. Colour = C50 (pink: words blur, grey: 0 dB, green: clear); size = RT60. Shading between seats is labelled as an estimate.
- **Fix:** a bullet bar of RT60 now vs target, with the area of each material needed.

## Run it on your phone

Phone browsers only allow the microphone and motion sensors on **https** pages. Put `index.html` in a GitHub
repository, enable **Settings → Pages → main / root**, and open `https://<user>.github.io/<repo>/` on the phone.
The included workflow (`.github/workflows/static.yml`) does the deploy automatically. Tap **Start** and allow
microphone and motion access. After the first load the app needs no internet (apart from the font, which falls back gracefully).

## How the numbers were checked

`python3 tests/test_dsp.py` runs **35 unit tests** in headless Chromium against the app's own functions, using
synthetic claps with a known RT60 (exponentially decaying noise over a background 55 dB lower). All pass:

| Check | Result |
|---|---|
| RT60 for rooms of 0.4 / 0.8 / 1.6 s | 0.403 / 0.802 / 1.600 s (within 1%) |
| RT60 at 44.1 kHz (phones differ) | 0.705 s for 0.7 s |
| RT60 with only 40 dB of headroom (tail correction) | 0.998 s for 1.0 s |
| C50 formula against theory, 10·log10(e^(0.05k) − 1) | within 0.25 dB |
| C50 over 12 random claps (no bias) | within 0.08 dB of theory |
| Clap 22 dB above background | rejected as too quiet |
| A second sound during the echo | rejected |
| ANSI S12.60 targets, Sabine area, round trip back to target RT | exact |

`python3 tests/test_e2e.py out_dir 0.8` plays synthetic claps through a fake microphone into the running app at
phone size (390×844), with simulated motion. A 0.8 s room measured 0.799–0.804 s at three seats, a 1.4 s room measured
1.41–1.43 s, and a clap with the phone moving was rejected. There were no console errors.

**On a real phone**, check that it repeats: two claps at the same seat should agree within about 10% (the Room table
shows the spread). If you can, compare one seat against a second phone or another acoustics app.

## Limits

- Claps carry little energy below 500 Hz, so the 250 Hz band is often too quiet. A popping balloon works better.
- Phones process audio differently. The app asks for raw audio and warns if the phone wouldn't switch processing off.
- The fix-it areas use Sabine's formula (sound spread evenly through the room) and typical absorption values
  (panels 0.9, curtains 0.5, carpet 0.3). Treat them as a starting estimate, not a specification.

## Suggested 1-minute video

1. (0–8 s) "Our classroom feels echoey. Can the back row actually understand the lecturer?" Open the app; the live aurora moves with room noise.
2. (8–22 s) Tap the front seat on the plan, put the phone down, tap Listen, walk to the front and clap. The phone buzzes; show RT60, C50 and the green checks.
3. (22–35 s) Scroll: the clap fading in the spectrogram, the decay curve with its fitted line, and RT60 by pitch against the 0.6 s target.
4. (35–48 s) Repeat at the back corner. Open **Room**: the back seat glows pink (words blur) while the front glows green.
5. (48–60 s) Open **Fix**: "We need about 11 m² of acoustic panels, or 21 m² of curtains." Close with: one clap per seat tells you who can't hear and what to buy.
