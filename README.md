# CPR Coach: smart glasses that coach chest compressions
<img width="520" height="304" alt="XR CPR Aura" src="https://github.com/user-attachments/assets/c02ac757-2e72-4cdb-88a7-b16e2caad5c0" />
<img width="1456" height="837" alt="image" src="https://github.com/user-attachments/assets/8ed24af5-370c-4508-badf-61ecb9a176ad" />



Software for an MSTI capstone at the University of Washington's Global Innovation Exchange (GIX), sponsored by MultiCare. Smart glasses watch someone practising CPR (cardiopulmonary resuscitation) on a manikin and coach them live: faster, slower, push harder, ease off, move your hands.

This repository holds the **measurement and coaching engine**: the code that turns what the glasses sense into rate, depth, fatigue and hand-position readings, and decides what to tell the person. The glasses app that will run it comes next.

> **Status (November 2026):** every piece is built and tested on *simulated* data only. The glasses and the Brayden Pro sensor manikin have not been used yet. Simulation shows the code works; it does not yet show that real head motion behaves the way the simulation assumes.

## Why this exists

73% of King County adults have been trained in CPR, but only 44% feel confident doing it (King County EMS community survey, 2021). People whose jobs require certification recertify every two years and rarely practise in between. The most common mistakes, compressions too shallow and too slow, are hard to feel.

The target for good adult compressions:

| Measure | Target |
| --- | --- |
| Rate | 100 to 120 a minute |
| Depth | 5 to 6 cm |
| Hands | Heel of the hand on the lower half of the breastbone |

## How it works

The glasses have no sensor on the chest. They know how the wearer's head moves and what the camera sees.

1. **Rate and pauses from head motion.** With arms locked, the head rises and falls once per compression. The engine counts those dips, works out the rate, and spots pauses.
2. **Depth from how far the head travels,** converted to chest depth with a calibration fitted against the manikin's true readings.
3. **Hand position from a printed chest marker.** The camera finds the marker, which sits a known distance from the correct hand position.
4. **A live coach** turns the readings into cues: it says "good" only when clearly inside the target, waits before correcting, and doesn't nag. A metronome ticks the target tempo and falls silent once the person holds it.
5. **A fatigue alert** compares each person's recent compressions with their own first 30 seconds, and reminds them to swap after two minutes.

During development, the Brayden Pro manikin records the true time and depth of every compression. That is the answer key the glasses are scored against. The coach itself never needs a manikin, so it also works for practice on a pillow.

## Quick start (Windows PowerShell)

Needs Python 3.11 or later.

```powershell
git clone https://github.com/<owner>/cpr-coach.git
cd cpr-coach
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
```

Then try the demos, all on simulated data:

```powershell
python run_demo.py --plot          # rate and pauses
python run_depth_demo.py --plot    # depth: one calibration for everyone vs one per person
python run_align_demo.py           # lining up the glasses and manikin clocks
python run_live_demo.py            # the live coach: delay, cue accuracy, prompts, metronome
python run_fatigue_demo.py         # fatigue alert
python run_marker_demo.py          # chest marker on generated camera frames
```

Score recorded sessions (simulated ones until real recordings exist):

```powershell
python make_sample_sessions.py --bench
python bench_report.py sessions\bench
```

Print the chest marker with `python make_marker_sheet.py` (or use `chest_marker.pdf`) at 100% scale.

## Results so far (simulation only)

| Piece | Result on simulated data |
| --- | --- |
| Rate | Within ±5 a minute in every 30-second window across 1,100 sessions (pass mark: 90% of windows) |
| Live detection | Each compression reported about 120 ms after its bottom |
| Clock alignment | No wrong alignment accepted in 2,000 runs; unclear cases are flagged, not guessed |
| Depth | About 2 mm error with a calibration per person; one shared calibration holds only while people differ by about 6% or less |
| Fatigue alert | Fired in all sessions that faded 25% or more; silent in all steady ones |
| Chest marker | Found at every distance, angle and light level tried on generated frames; lost with heavy motion blur |

<img width="1560" height="845" alt="rate_detection" src="https://github.com/user-attachments/assets/aea6f7e8-b0ba-442b-83d2-ab0858157827" />
<img width="1500" height="690" alt="live_coach" src="https://github.com/user-attachments/assets/14d93782-05e3-47c3-88ce-a79cc28c4941" />
<img width="1170" height="676" alt="depth_calibration" src="https://github.com/user-attachments/assets/f6cceae8-72d5-4dd1-8ea2-df8cfa79dd9a" />
<img width="1500" height="660" alt="fatigue_alert" src="https://github.com/user-attachments/assets/7f47fabc-36d7-4f12-b558-26e0b324dd60" />
<img width="1500" height="630" alt="marker_blur" src="https://github.com/user-attachments/assets/afe9f58c-ffbd-49e8-9104-d94219ddfe2d" />

## Repository layout

| Path | What's there |
| --- | --- |
| `cpr_engine/` | The engine: rate, depth, alignment, live detector, coach, fatigue, chest marker, scoring, simulators |
| `run_*.py` | Demos that print results on simulated data |
| `score_session.py`, `bench_report.py`, `fit_calibration.py` | Tools for recorded sessions |
| `make_sample_sessions.py`, `make_marker_sheet.py` | Generate sample sessions and the printable marker |
| `tests/` | 222 automated tests |
| `docs/TECHNICAL_GUIDE.md` | How each piece works, in detail |
| `docs/SESSION_FORMAT.md` | The file format the glasses capture app and the manikin converter must write |

## What comes next

- **Capture app** (Unity, on the XREAL 1 Pro+ with the Eye camera) to record real sessions.
- **Brayden converter**, once a real export file is in hand.
- **Hand detection** from real video, to feed the hand-position check.
- **Bench test** on 20 real sessions against the Brayden Pro.
- **Glasses app**: the live detector and coach translated to C# for Unity, on the 1 Pro+ and then the XREAL Aura.

## Team

Coleman Bryant, Yan Zhang and Youngpyung, MSTI Connected Devices track, GIX. Sponsored by MultiCare.
