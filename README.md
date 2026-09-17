# BirdMan

A picture frame that shows the birds heard in the yard today.

A microphone near the feeder listens all day. Each recording is identified with
[BirdNET](https://github.com/birdnet-team/birdnet). The first time a species is heard, a
woodblock-style illustration is generated for it. The birds are packed into a honeycomb
collage and shown on a six-colour e-ink display. As new species turn up the flock grows;
at midnight the frame goes back to *listening…* and the next day starts fresh.

**Status: proof of concept.** The whole pipeline runs on a Mac using xeno-canto recordings
in place of a microphone. Nothing has run on a Raspberry Pi or a real panel yet. See
[Roadmap](#roadmap) for what stands between this and a frame on the wall.


## How it works

```
recording ─▶ detect ─▶ heard ─▶ art ─▶ collage ─▶ eink ─▶ panel
 (inbox/)   BirdNET   today's  Gemini   packer    dither   Inky
                       list
```

| Step | Module | What it does |
|---|---|---|
| Listen | *(not written yet)* | Will write 15-second WAV files into `data/inbox/`. Today `dev/simulate.py` plays this part. |
| Detect | `detect.py` | Runs BirdNET on one clip. Keeps species at or above `MIN_CONF`, filtered to species plausible for the configured location and week. Drops non-birds (insects, frogs, engines…). |
| Remember | `heard.py` | Today's species with first/last heard, best confidence and count, saved to `data/state/heard.json`. Empties itself when the date changes. |
| Illustrate | `art.py` | One Gemini image per species, saved in `assets/art/` and reused forever. `cutout()` removes the paper background whatever shade it came back as. |
| Compose | `collage.py` | Packs the bird silhouettes tightly around a central "hero" (the first bird of the day). Works for 0 to 15 birds. Birds keep their size, facing and side of the hero all day, so the flock grows instead of reshuffling. |
| Convert | `eink.py` | Dithers against the panel's *real* ink colours, then outputs pure primaries for the device plus a preview of how it should look on the wall. Text is stamped on afterwards in solid black so it stays sharp. |
| Display | `panel.py` | Pushes to the Inky if one is attached. On a laptop it quietly reports `no panel`. |
| Orchestrate | `watch.py` | The always-on loop that ties it together. |

The contract between "the microphone" and "everything else" is simply **audio files appearing
in `data/inbox/`**. Anything that can put files there can be the microphone: the simulator, a
recorder on the same Pi, or a second device sending clips over Wi-Fi.


## Project layout

```
BirdMan/
├── pyproject.toml
├── uv.lock
├── .env                    # GOOGLE_API_KEY — never committed
├── src/birdman/            # the application
│   ├── config.py           # settings and every path, anchored to the project root
│   ├── clock.py            # the one clock (can be faked for testing midnight)
│   ├── detect.py
│   ├── heard.py
│   ├── art.py
│   ├── collage.py
│   ├── eink.py
│   ├── panel.py
│   ├── watch.py            # entry point: birdman-watch
│   └── render_once.py      # entry point: birdman-render
├── assets/                 # things you own — committed
│   ├── art/                # one PNG per species. NOT a cache: see below
│   └── fonts/              # Cormorant Garamond (regular + italic, variable)
├── data/                   # everything the program writes — gitignored, safe to delete
│   ├── inbox/              # recordings waiting to be analysed
│   ├── state/heard.json
│   ├── history/            # a snapshot of every frame update (last 500)
│   ├── out/                # frame.png, frame_preview.png, live.html
│   └── local_species.txt   # location filter, rebuilt if missing
└── dev/                    # never deployed
    ├── simulate.py         # the fake microphone
    └── clips/              # xeno-canto test recordings
```

**`assets/art/` is precious.** The same prompt gives a different bird every time, so an
illustration you like cannot be regenerated. Keep this folder in git.


## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync
```

Create `.env` in the project root:

```
GOOGLE_API_KEY=your-key-here
```

Put the two Cormorant Garamond variable-font files in `assets/fonts/`, and some bird
recordings (wav, mp3, flac or ogg) in `dev/clips/`.

Then set your location in `src/birdman/config.py` (`LAT`, `LON`, and `WEEK`). BirdNET counts
48 weeks a year, four per month. Delete `data/local_species.txt` after changing any of them so
the species filter is rebuilt.

> **PyCharm:** right-click `src` → *Mark Directory as* → *Sources Root*. Imports are always
> `from birdman.x import …`, never `from src.birdman…`.

> **Inky on a Mac:** it cannot be installed (it compiles against Linux headers). It is declared
> as a Linux-only dependency, so `uv sync` skips it on macOS and installs it on the Pi.


## Running it

Two terminals.

```bash
# 1 — the watcher. --fresh forgets anything heard earlier today.
uv run birdman-watch --fresh

# 2 — the fake microphone: one clip every 20 seconds, random order
uv run dev/simulate.py --every 20 --shuffle
```

Then watch the frame change:

```bash
open data/out/live.html
```

The page reloads the preview every two seconds. Every update is also saved in
`data/history/`, so you can flip through the day afterwards.

To render a single frame without the watcher:

```bash
uv run birdman-render --demo     # six hard-coded species, no audio analysis
uv run birdman-render            # analyse everything in dev/clips/
```

`birdman-render` only writes image files; pushing to the panel is the watcher's job.

### Reading the watcher's log

```
XC682547 - Northern Cardinal….mp3: []   best: Northern Cardinal (0.67)
```

means BirdNET's best guess was a cardinal at 0.67, which is under `MIN_CONF` (0.7), so
nothing was added. `no panel (ModuleNotFoundError)` is normal on a laptop.

### Watcher options

| Flag | Default | Purpose |
|---|---|---|
| `--fresh` | off | Start the day empty. Use for test runs. |
| `--settle N` | 0 | After a new species, wait N seconds for others before redrawing, so a dawn chorus becomes one update. Try 30. |
| `--min-gap N` | 0 | Never redraw more often than every N seconds. Try 180 on a real panel, which is slow to refresh. |

### Simulator options

`--every N` seconds between clips · `--shuffle` · `--rounds N` to replay the library
(repeats should cause no redraws).


## Testing recipes

**Midnight in 30 seconds.** The clock can be started at any moment and ticks forward from
there:

```bash
BIRDMAN_NOW="2026-09-17 23:59:30" uv run birdman-watch --fresh
```

Start the simulator straight away. Birds appear, then `--- new day ---` is logged and the
frame returns to *listening…*.

**Gemini unavailable.** Blank the key in `.env` and delete one PNG from `assets/art/`. That
species should still be named in the caption, its picture should be absent, and the log should
say it will retry in 10 minutes. Nothing is cached on failure.

**Bursts.** `uv run dev/simulate.py --every 2` against
`uv run birdman-watch --fresh --settle 10 --min-gap 60` should produce one or two redraws,
not one per clip.

**Corrupt state.** Truncate `data/state/heard.json` by hand and start the watcher. It should
start the day fresh and keep the bad file as `heard.corrupt.json`.

**Restart mid-day.** Stop the watcher and start it again without `--fresh`. Today's flock
should come straight back.

**Things that should show nothing.** Feed it silence, rain, speech, a dog, a lawnmower. A
wrong bird on the wall all day is the failure that matters most.


## Tuning

| Where | Setting | Effect |
|---|---|---|
| `config.py` | `MIN_CONF` | Confidence needed to count as heard. |
| `config.py` | `W, H` | Panel resolution. 800×480 is the Inky Impression 7.3". |
| `collage.py` | `GAP` | Pixels of paper between neighbouring birds. |
| `collage.py` | `SMALL` | Size of supporting birds relative to the hero. |
| `collage.py` | `ANGLE_PULL` | 0 = tightest blob; higher = birds spread more evenly around the hero. |
| `collage.py` | `FINE_BOOST` | Weight of the small text. Raise if thin, lower if letters fill in. |
| `collage.py` | `MAX_BIRDS` | Birds drawn. Extra species become "+ N more" in the caption. |
| `eink.py` | `PANEL` | Estimated real ink colours. **Calibrate against the physical panel.** |
| `eink.py` | `SATURATION`, `CONTRAST` | Pre-dither punch. |
| `art.py` | `prompt_for`, `POSES` | The illustration style. Changing it only affects species not yet in `assets/art/`. |

The layout constants in `collage.py` are in pixels and tuned for 800×480. A different panel
size needs them revisited.


## Hardware plan

Nothing here is built yet.

- **Frame (indoors):** Raspberry Pi 4 + Inky Impression 7.3" (2025 Edition), 15 W USB-C
  supply, stick-on heatsinks, high-endurance microSD. Raspberry Pi OS Lite, 64-bit.
- **Memory:** BirdNET analyses in worker processes; combined peak measured on the Mac was
  about 1.7 GB. 2 GB is not enough. 3 GB works with the Lite OS; 4 GB is comfortable.
- **Microphone:** an omnidirectional USB lavalier.
- **Outdoor unit:** the feeder is about 30 ft from the house, so a second small device will
  sit at the pergola in a weatherproof box, record, and send clips into the frame Pi's
  `data/inbox/` over Wi-Fi. Candidates: a Raspberry Pi 3 Model B (simplest) or an ESP32 with
  ready-made streaming firmware (smaller, no SD card, far less power). Needs power and a
  usable Wi-Fi signal at the pergola.
- **First real-world test:** the Pi 4 alone in the weatherproof box at the pergola with the
  mic, running the whole pipeline, checked from a laptop over Wi-Fi. No Inky required.


## Roadmap

To reach "runs on the wall for a week untouched":

1. **Recorder**: live microphone → 15-second, 48 kHz mono WAVs in `data/inbox/`.
2. **Services**: systemd units so recording and watching start on boot and restart on failure.
3. **First run on the Pi**: enable SPI/I2C, push a frame, calibrate `PANEL` colours.
4. **"Heard twice" rule**: accept a species at ≥ 0.7 once, or ≥ 0.5 twice. Rescues near
   misses, blocks one-off strays.
5. **Automatic `WEEK`** so the species filter follows the seasons.
6. **Evidence clips**: keep the recording behind each new species so surprises can be
   listened to.
7. **Pre-generated, reviewed art** for every species in `local_species.txt`, ideally with a
   reference photo in the prompt for accuracy, so the wall never waits on Gemini.
8. **Sender** for the outdoor unit.

Later: long-term history, a small website, capping BirdNET's worker processes to save memory.


## Troubleshooting

| Symptom | Cause |
|---|---|
| `ModuleNotFoundError: No module named 'config'` (or `art`, `clock`…) | An import is missing the `birdman.` prefix. |
| `No module named 'src'` | An import starts with `src.`. Remove it. |
| `No module named 'birdman'` | The package isn't installed. Check the `[build-system]` and `[tool.hatch…]` sections of `pyproject.toml`, then `uv sync`. |
| `pip install inky` fails on macOS | Expected. Inky is Linux-only and not needed on a laptop. |
| Birds spaced far apart, stray dots around them | New artwork came back on off-white paper. `cutout()` handles this; make sure you have the current `art.py`. |
| Fewer birds than clips | Those clips scored under `MIN_CONF`, or the species isn't in `data/local_species.txt`. The log shows each clip's best guess. |
| Different birds than last time | The PNGs in `assets/art/` were regenerated. Restore them from git. |
| `live.html` never changes | You opened an old copy. The live one is `data/out/live.html`. |


## Credits

- Species identification: [BirdNET](https://github.com/birdnet-team/birdnet), K. Lisa Yang
  Center for Conservation Bioacoustics, Cornell Lab of Ornithology, and Chemnitz University of
  Technology.
- Test recordings: [xeno-canto](https://xeno-canto.org) contributors. Each recording carries
  its own Creative Commons licence.
- Typeface: Cormorant Garamond by Christian Thalmann (SIL Open Font License).
- Display library: [Pimoroni Inky](https://github.com/pimoroni/inky).
- Inspiration for the collage: [AvianVisitors](https://github.com/Twarner491/AvianVisitors).
  No code or artwork from that project is used here.