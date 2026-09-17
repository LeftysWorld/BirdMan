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
recording ─▶ detect ─▶ state ─▶ illustrate ─▶ cutout ─▶ collage ─▶ eink ─▶ panel
 (inbox/)    BirdNET   today's     Gemini      remove     packer    dither   Inky
                        list                   paper
```

There is no agent here. Nothing decides what to do next: a recording arrives and the same
steps run in the same order. Two of those steps call an AI model. The code is organised
around that.

| Folder | Holds | Rule |
|---|---|---|
| `models/` | The two AI models: `BirdNet` and `GeminiImages`. Loading, versions, the raw call. | Knows nothing about birds, thresholds or files. Swap a model by editing one file. |
| `context/` | What the models are given: the illustration prompts, the local species list, the non-bird filter. | No API code. Change the look of the art or the filter here. |
| `steps/` | One job each: detect, illustrate, cutout, collage, eink, panel. | Steps do not know about each other (one exception: `collage` asks `illustrate` and `cutout` for each bird). |
| `app/` | The loop that runs the steps in order. | The only code that knows the sequence. |
| `state.py` | Today's heard list, saved to disk. | Current and disposable. It is state, not memory: a long-term history would be a separate thing. |
| `records.py` | The data classes that travel between the parts above. | Plain data, no pipeline logic. |

Dependencies point one way:

```
app  ─▶  steps, state  ─▶  models, context  ─▶  records, config, clock
```

(`context/species.py` reaches into `models/birdnet.py` to build the species list. That is the
one place `context` and `models` are not side by side.)

The contract between "the microphone" and "everything else" is simply **audio files appearing
in `data/inbox/`**. Anything that can put files there can be the microphone: the simulator, a
recorder on the same Pi, or a second device sending clips over Wi-Fi.

### The data classes

| Class | Where | What it is |
|---|---|---|
| `Prediction` | `records.py` | One raw line of BirdNET output: `label` ("Scientific_Common") and `confidence`, with `.common` and `.scientific`. |
| `Detection` | `records.py` | A bird accepted as heard in one recording: `species`, `confidence`. |
| `SpeciesRecord` | `records.py` | One species in today's list: `first_heard`, `last_heard`, `best_confidence`, `count`. |
| `Heard` | `state.py` | Today's list. `add(detections)` returns the species that are new; `roll_over()` empties it when the date changes. |
| `BirdPlan`, `Placement` | `steps/collage.py` | Private to the packer: how a bird should appear today, and where it landed. |

`heard.json` keeps short keys (`first`, `last`, `conf`, `count`) on disk; the longer names
exist only in code. `records.py` is deliberately not called `types.py`, which would shadow
Python's own `types` module for any script run from inside that folder.


## Project layout

```
BirdMan/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env                        # GOOGLE_API_KEY. Gitignored. Never commit this.
├── .gitignore
│
├── src/birdman/
│   ├── config.py               # settings and every path, anchored to the project root
│   ├── clock.py                # the one clock (can be faked to test midnight)
│   ├── records.py              # Prediction, Detection, SpeciesRecord
│   ├── state.py                # Heard: today's list
│   ├── models/
│   │   ├── birdnet.py          # class BirdNet
│   │   └── gemini.py           # class GeminiImages
│   ├── context/
│   │   ├── prompts.py          # POSES, prompt_for, plate_prompt
│   │   └── species.py          # local species list, non-bird filter
│   ├── steps/
│   │   ├── detect.py           # recording -> list[Detection]
│   │   ├── illustrate.py       # species -> artwork file
│   │   ├── cutout.py           # artwork -> bird with the paper removed
│   │   ├── collage.py          # birds -> composed frame + text mask
│   │   ├── eink.py             # frame -> device image + wall preview
│   │   └── panel.py            # device image -> Inky
│   └── app/
│       ├── watch.py            # entry point: birdman-watch
│       └── render_once.py      # entry point: birdman-render
│
├── assets/                     # things you own. Committed.
│   ├── art/                    # one PNG per species. NOT a cache: see below
│   └── fonts/                  # Cormorant Garamond (regular + italic, variable)
│
├── data/                       # everything the program writes. Gitignored, safe to delete.
│   ├── inbox/                  # recordings waiting to be analysed
│   ├── state/heard.json
│   ├── history/                # a snapshot of every frame update (last 500)
│   ├── out/                    # frame.png, frame_preview.png, live.html
│   └── local_species.txt       # location filter, rebuilt if missing
│
└── dev/                        # never deployed
    ├── simulate.py             # the fake microphone
    └── clips/                  # xeno-canto test recordings
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
> `from birdman.x import …`, never `from src.birdman…`. When moving files, use
> *Refactor → Move* so imports are rewritten for you.

> **Committing:** PyCharm's commit dialog force-adds any file you tick, even ignored ones.
> Check the *Unversioned Files* list before committing so `.env` never goes in.

> **Inky on a Mac:** it cannot be installed (it compiles against Linux headers). Declare it
> as a Linux-only dependency, `uv add "inky; sys_platform == 'linux'"`, so `uv sync` skips
> it on macOS and installs it on the Pi.


## Running it

Two terminals.

```bash
# 1 - the watcher. --fresh forgets anything heard earlier today.
uv run birdman-watch --fresh

# 2 - the fake microphone: one clip every 20 seconds, random order
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

`--every N` seconds between clips, `--shuffle`, and `--rounds N` to replay the library
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
species should still be named in the caption, its picture should be absent, the log should say
`gemini failed for …: MissingApiKey`, and it should retry in 10 minutes. Nothing is cached on
failure, and nothing crashes on start-up.

**Bursts.** `uv run dev/simulate.py --every 2` against
`uv run birdman-watch --fresh --settle 10 --min-gap 60` should produce one or two redraws,
not one per clip.

**Corrupt state.** Truncate `data/state/heard.json` by hand and start the watcher. It should
start the day fresh and keep the bad file as `heard.corrupt.json`.

**Restart mid-day.** Stop the watcher and start it again without `--fresh`. Today's flock
should come straight back.

**Things that should show nothing.** Feed it silence, rain, speech, a dog, a lawnmower. A
wrong bird on the wall all day is the failure that matters most.

**Memory.** `/usr/bin/time -l` only reports the largest single process and BirdNET analyses
in worker processes, so it under-reports. Sum every process instead while a render runs:

```bash
while true; do ps -axo rss,command | grep "[B]irdMan" | awk '{s+=$1} END {printf "%.0f MB\n", s/1024}'; sleep 1; done
```


## Tuning

| Where | Setting | Effect |
|---|---|---|
| `config.py` | `MIN_CONF` | Confidence needed to count as heard. |
| `config.py` | `W, H` | Panel resolution. 800×480 is the Inky Impression 7.3". |
| `config.py` | `GEMINI_MODEL` | Which Gemini image model is called. |
| `context/prompts.py` | `prompt_for`, `POSES` | The illustration style. Only affects species not yet in `assets/art/`. |
| `context/species.py` | `GEO_MIN` | How likely a species must be at your location to make the local list. |
| `context/species.py` | `NON_BIRD` | Labels that are never shown (insects, frogs, engines…). |
| `steps/collage.py` | `GAP` | Pixels of paper between neighbouring birds. |
| `steps/collage.py` | `SMALL` | Size of supporting birds relative to the hero. |
| `steps/collage.py` | `ANGLE_PULL` | 0 = tightest blob; higher = birds spread more evenly around the hero. |
| `steps/collage.py` | `FINE_BOOST` | Weight of the small text. Raise if thin, lower if letters fill in. |
| `steps/collage.py` | `MAX_BIRDS` | Birds drawn. Extra species become "+ N more" in the caption. |
| `steps/eink.py` | `PANEL` | Estimated real ink colours. **Calibrate against the physical panel.** |
| `steps/eink.py` | `SATURATION`, `CONTRAST` | Pre-dither punch. |

The layout constants in `collage.py` are in pixels and tuned for 800×480. A different panel
size needs them revisited.


## Hardware plan

Nothing here is built yet.

- **Frame (indoors, on the wall):** Raspberry Pi 4 + Inky Impression 7.3" (2025 Edition),
  15 W USB-C supply, stick-on heatsinks, high-endurance microSD. Raspberry Pi OS Lite, 64-bit.
- **Memory:** combined peak measured on the Mac was about 1.7 GB across BirdNET's worker
  processes. 2 GB is not enough. 3 GB works with the Lite OS; 4 GB is comfortable.
- **Microphone:** an omnidirectional USB lavalier.
- **Outdoor unit:** the feeder is about 30 ft from the house, so a second small device sits
  at the pergola in a weatherproof box, records, and sends clips into the frame Pi's
  `data/inbox/` over Wi-Fi. Leaning towards a Raspberry Pi 3 Model B (simplest: same OS, USB
  mic plugs straight in, clips queue if Wi-Fi drops). An ESP32 with ready-made RTSP
  streaming firmware is the smaller, lower-power alternative, and the better choice if
  there is no outlet nearby. Either way it needs power and a usable Wi-Fi signal out there.
- **Weatherproofing:** an outdoor cord-connection box under the pergola roof, cables exiting
  at the bottom with a drip loop, mic capsule facing down, a silica gel packet inside.
- **First real-world test:** the Pi 4 alone in that box at the pergola with the mic, running
  the whole pipeline overnight, checked from a laptop over Wi-Fi in the morning. No Inky and
  no second device required.


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

Later: long-term history (real memory, separate from `state.py`), a small website, capping
BirdNET's worker processes to save memory. An art-quality loop (generate, have a vision model
check the species, retry) would be a genuine agent workflow, and belongs in a separate
dev-side tool rather than on the frame.


## Troubleshooting

| Symptom | Cause |
|---|---|
| `No module named 'birdman.art'` (or `.heard`, `.detect`, `.collage`…) | An import still points at the old flat layout. Find them all with `grep -rnE "from birdman\.(art\|heard\|detect\|collage\|eink\|panel\|watch) import" src dev` |
| `No module named 'config'` (or `clock`, `state`…) | An import is missing the `birdman.` prefix. |
| `No module named 'src'` | An import starts with `src.`. Remove it. |
| `No module named 'birdman'` | The package isn't installed. Check the `[build-system]` and `[tool.hatch…]` sections of `pyproject.toml`, then `uv sync`. |
| `project.name field is not set` | `pyproject.toml` lost its `[project]` section. `uv.lock` still lists the original dependencies under `requires-dist`. |
| `gemini failed for …: MissingApiKey` | `.env` is missing, empty, or not in the project root. |
| `pip install inky` fails on macOS | Expected. Inky is Linux-only and not needed on a laptop. |
| GitHub rejects the push: "Push cannot contain secrets" | `.env` is in a commit. Removing it in a new commit is not enough; it has to come out of history. Never use the "allow the secret" link. |
| Birds spaced far apart, stray dots around them | New artwork came back on off-white paper. `cutout()` handles this; make sure `steps/cutout.py` is current. |
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