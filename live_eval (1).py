"""Check the live detector and coach against the truth.

Replays a recording through the live detector and coach as if it were
happening now, and compares what the coach showed and said with what
the truth called for. Works on a simulated session, or on a recorded
one once the manikin's times are on the glasses clock (the bench
report does this).

`sim` is anything with: t, y (head height samples), true_times and
true_depths_m (one entry per true compression).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .coach import CoachConfig, run_live
from .depth import fit_calibration, head_travel
from .rate import detect_compressions, rate_in_window
from .scoring import pair_events
from .simulate import simulate_session

TICK_S = 0.1          # how often the coach's output is checked
TRUTH_WINDOW_S = 5.0  # the true rate is taken over this long


@dataclass
class LiveResult:
    delay_ms: float               # typical time from the bottom of a compression to its report
    n_missed: int
    n_extra: int
    rate_right: float             # share of checked moments where the rate cue was the right one
    rate_false_good: float        # share where it said "good" and the true rate was out of range
    rate_wrong_way: float         # share where it said faster/slower and the truth was the opposite
    rate_needless: float          # share where it corrected and the true rate was in range
    depth_right: float            # the same four for depth (NaN with no calibration)
    depth_false_good: float
    depth_wrong_way: float
    depth_needless: float
    first_correction_s: float     # time from the first compression to the first spoken correction
    prompts_per_min: float
    prompts: list                 # (time, words)
    metronome_on: float = 0.0     # share of the session the tick was sounding
    metronome_spans: list = None  # (start, end) of each stretch it sounded


def evaluate_live(sim, calibration=None, config: CoachConfig | None = None) -> LiveResult:
    cfg = config or CoachConfig()
    comps, states = run_live(sim.t, sim.y, calibration, cfg)

    est = np.array([c.t for c in comps])
    ei, ti = pair_events(est, sim.true_times)
    delays = [comps[i].detected_at - sim.true_times[j] for i, j in zip(ei, ti)]

    # Check the cues on an even time grid.
    state_t = np.array([s.t for s in states])
    ticks = np.arange(state_t[0], state_t[-1], TICK_S)
    idx = np.clip(np.searchsorted(state_t, ticks), 0, len(states) - 1)

    r_lo, r_hi = cfg.good_rate_cpm
    d_lo, d_hi = cfg.good_depth_m
    rate = _Tally()
    depth = _Tally()
    for tk, i in zip(ticks, idx):
        s = states[i]
        true_rate = rate_in_window(sim.true_times, tk - TRUTH_WINDOW_S, tk)
        if not np.isnan(true_rate):
            rate.add(
                s.rate_cue,
                low=true_rate < r_lo,
                high=true_rate > r_hi,
                clearly_good=r_lo + cfg.rate_margin_cpm <= true_rate <= r_hi - cfg.rate_margin_cpm,
                names=("faster", "slower"),
            )
        if calibration is not None and sim.true_depths_m is not None:
            done = np.searchsorted(sim.true_times, tk)
            n = cfg.depth_over_n
            if done >= n and tk - sim.true_times[done - 1] < cfg.pause_s:
                true_depth = float(np.median(sim.true_depths_m[done - n:done]))
                depth.add(
                    s.depth_cue,
                    low=true_depth < d_lo,
                    high=true_depth > d_hi,
                    clearly_good=d_lo + cfg.depth_margin_m <= true_depth <= d_hi - cfg.depth_margin_m,
                    names=("push harder", "ease off"),
                )

    prompts = [(s.t, s.prompt) for s in states if s.prompt]
    corrections = [t for t, words in prompts if not words.startswith("Good")]
    first = corrections[0] - sim.true_times[0] if corrections and sim.true_times.size else float("nan")
    minutes = (state_t[-1] - state_t[0]) / 60.0

    on = np.array([s.metronome_on for s in states], dtype=bool)
    spans = []
    edges = np.flatnonzero(np.diff(np.concatenate(([False], on, [False])).astype(int)))
    for a, b in zip(edges[::2], edges[1::2]):
        spans.append((float(state_t[a]), float(state_t[min(b, len(state_t) - 1)])))

    return LiveResult(
        delay_ms=float(np.median(delays) * 1000.0) if delays else float("nan"),
        n_missed=int(sim.true_times.size - ei.size),
        n_extra=int(est.size - ei.size),
        rate_right=rate.right(),
        rate_false_good=rate.false_good(),
        rate_wrong_way=rate.wrong_way(),
        rate_needless=rate.needless(),
        depth_right=depth.right(),
        depth_false_good=depth.false_good(),
        depth_wrong_way=depth.wrong_way(),
        depth_needless=depth.needless(),
        first_correction_s=float(first),
        prompts_per_min=len(prompts) / minutes if minutes > 0 else float("nan"),
        prompts=prompts,
        metronome_on=float(on.mean()),
        metronome_spans=spans,
    )


def simulated_calibration(head_gain: float = 0.9, coupling_jitter: float = 0.04, seed: int = 500):
    """A depth calibration fitted the way a real one would be: from a sweep session."""
    sweep = simulate_session(
        duration_s=90, start_cue=3, depth_m=0.035, depth_drift_m=0.035, depth_jitter=0.05,
        head_gain=head_gain, head_coupling_jitter=coupling_jitter, seed=seed,
    )
    est = detect_compressions(sweep.t, sweep.y)
    travel = head_travel(sweep.t, sweep.y, est)
    ei, ti = pair_events(est, sweep.true_times)
    return fit_calibration(travel[ei], sweep.true_depths_m[ti])


class _Tally:
    """Counts how often a cue agreed with the truth."""

    def __init__(self):
        self.n = 0              # moments with a true reading
        self.n_clear = 0        # moments where the truth clearly calls for one cue
        self.n_right = 0
        self.n_false_good = 0
        self.n_wrong_way = 0
        self.n_needless = 0

    def add(self, cue: str, low: bool, high: bool, clearly_good: bool, names) -> None:
        up, down = names        # the cue for "too low" and the cue for "too high"
        self.n += 1
        if cue == "good" and (low or high):
            self.n_false_good += 1
        if (cue == up and high) or (cue == down and low):
            self.n_wrong_way += 1
        if cue in (up, down) and not (low or high):
            self.n_needless += 1
        if low or high or clearly_good:
            self.n_clear += 1
            wanted = up if low else down if high else "good"
            self.n_right += cue == wanted

    def right(self) -> float:
        return self.n_right / self.n_clear if self.n_clear else float("nan")

    def false_good(self) -> float:
        return self.n_false_good / self.n if self.n else float("nan")

    def wrong_way(self) -> float:
        return self.n_wrong_way / self.n if self.n else float("nan")

    def needless(self) -> float:
        return self.n_needless / self.n if self.n else float("nan")


@dataclass
class FatigueResult:
    alert_s: float            # time of the first "tiring" prompt (NaN if none)
    true_fade_s: float        # time the true depth had fallen by the alert share (NaN if never)
    measured_decline: float   # the monitor's last reading of the decline
    true_decline: float       # the true decline in depth by the end
    swap_s: list              # times of the swap reminders
    prompts: list             # every prompt: (time, words)


def evaluate_fatigue(sim, calibration=None, config: CoachConfig | None = None) -> FatigueResult:
    """Replay a session and compare the fatigue alert with the true fade in depth."""
    from .coach import PROMPTS

    cfg = config or CoachConfig()
    fc = cfg.fatigue
    _, states = run_live(sim.t, sim.y, calibration, cfg)
    prompts = [(s.t, s.prompt) for s in states if s.prompt]
    alerts = [t for t, w in prompts if w == PROMPTS["tiring"]]
    swaps = [t for t, w in prompts if w == PROMPTS["swap"]]
    declines = [s.decline for s in states if s.decline == s.decline]

    # The truth, worked out the same way from the true depths.
    t_true, d_true = sim.true_times, sim.true_depths_m
    start = t_true[t_true <= t_true[0] + fc.baseline_s]
    baseline = float(np.median(d_true[: start.size]))
    true_fade = float("nan")
    n = fc.recent_n
    for k in range(start.size + n, t_true.size + 1):
        if np.median(d_true[k - n:k]) <= (1.0 - fc.decline) * baseline:
            true_fade = float(t_true[k - 1])
            break
    true_decline = 1.0 - float(np.median(d_true[-n:])) / baseline

    return FatigueResult(
        alert_s=alerts[0] if alerts else float("nan"),
        true_fade_s=true_fade,
        measured_decline=declines[-1] if declines else float("nan"),
        true_decline=true_decline,
        swap_s=swaps,
        prompts=prompts,
    )
