"""Tune the mixer signal filter.

The user's complaint: with the slider parked, the displayed value drifts by a
couple of units on its own (26 -> 28 -> 27).  That is ADC noise being tracked by
a filter that is fast by design.

This harness models the hardware, then measures each filter on:

  * **jitter**  - how much the *output* moves while the *input* is parked.  This
                  is the number that matters to the user; the old chain had a
                  small EMA jitter that occasionally crossed a quantisation
                  boundary and produced visible 2-unit hops.
  * **lag**     - samples to reach 90% of a step for a deliberate move, and the
                  overshoot on arrival.  This is what "cutting functionality"
                  would mean, so it is constrained.

Run with::

    python tests/tune_filter.py
"""

import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from collections import deque

from controllers.serial_controller import (
    AdaptiveEMA,
    FastCascadedFilter,
    MedianFilter,
)

#: The mixer reports roughly 20 packets/second, so one sample is ~50 ms.
SAMPLE_MS = 50

#: Quantisation the application applies (VolumeManager.STEP).
STEP = 2


def quantise(value):
    """What the UI/audio path finally uses."""
    clamped = max(0, min(100, value))
    return int(round(clamped / STEP) * STEP)


def park_signal(samples, level=27.0, noise=1.4, seed=1):
    """A parked slider: the true value is constant, the reading is noisy."""
    rng = random.Random(seed)
    return [level + rng.gauss(0, noise) for _ in range(samples)]


def step_signal(before=30.0, after=60.0, samples=200, noise=1.4, seed=2):
    """A deliberate move: hold, jump, hold."""
    rng = random.Random(seed)
    values = []
    for index in range(samples):
        true = before if index < 40 else after
        values.append(true + rng.gauss(0, noise))
    return values


def run(filter_factory, signal):
    """Feed *signal* through a fresh filter and return quantised outputs."""
    instance = filter_factory()
    return [quantise(instance.filter(value)) for value in signal]


def jitter_stats(outputs, ignore=60):
    """Movement of a parked output, measured after the filter has settled."""
    settled = outputs[ignore:]
    changes = sum(1 for a, b in zip(settled, settled[1:]) if a != b)
    return {
        "distinct": len(set(settled)),
        "range": max(settled) - min(settled),
        "changes": changes,
        "stdev": round(statistics.pstdev(settled), 2) if len(settled) > 1 else 0.0,
    }


def step_stats(outputs, before=30, after=60, step_at=40):
    """Samples to reach 90% of a step, and any overshoot past the target."""
    target = quantise(after)
    start = quantise(before)
    direction = 1 if target > start else -1
    threshold = start + direction * abs(target - start) * 0.9

    reached = None
    for offset, value in enumerate(outputs[step_at:], start=step_at):
        if (direction > 0 and value >= threshold) or (direction < 0 and value <= threshold):
            reached = offset - step_at + 1
            break

    settled = outputs[step_at + 30 :]
    overshoot = 0
    if settled:
        if direction > 0:
            overshoot = max(0, max(settled) - target)
        else:
            overshoot = max(0, target - min(settled))

    return {
        "samples_to_90%": reached if reached is not None else "never",
        "lag_ms": (reached * SAMPLE_MS) if reached is not None else None,
        "overshoot": overshoot,
    }


# --------------------------------------------------------------------- filters
class CurrentFilter:
    """The filter as shipped: adaptive EMA followed by a median of 5."""

    def __init__(self):
        self.inner = FastCascadedFilter()

    def filter(self, value):
        return self.inner.filter(value)


class MedianThenEMA:
    """Median (spike rejection) then a mild EMA (smooth transitions)."""

    def __init__(self, median_window=7, alpha=0.25):
        self.median = MedianFilter(window_size=median_window)
        self.alpha = alpha
        self.value = None

    def filter(self, new_value):
        med = self.median.filter(new_value)
        if self.value is None:
            self.value = med
        else:
            self.value = self.alpha * med + (1 - self.alpha) * self.value
        return self.value


class AdaptiveSlew:
    """Median, then a drift-aware deadband stage.

    ``deadband`` is in slider units: while the incoming reading stays within it
    of the latched output, the output does not move at all - that is what kills
    parked jitter.  The catch is that a deadband alone also lags a slow, genuine
    sweep, so a second, long median estimates whether the signal is actually
    drifting.  Noise around a parked value has a long median on the latched
    value; a real sweep moves it.  When drift is detected the deadband collapses
    and the output tracks closely, so no functionality is lost.
    """

    def __init__(
        self,
        median_window=7,
        long_window=25,
        deadband=1.6,
        drift_threshold=0.7,
        big_jump=8.0,
        fast_alpha=0.5,
        slow_alpha=0.2,
        track_step_ratio=0.4,
    ):
        self.median = MedianFilter(window_size=median_window)
        self.long_median = MedianFilter(window_size=long_window)
        self.deadband = deadband
        self.drift_threshold = drift_threshold
        self.big_jump = big_jump
        self.fast_alpha = fast_alpha
        self.slow_alpha = slow_alpha
        # While tracking, the latched value follows the smoother at this
        # fraction of the deadband, so an intentional move is not smoothed away.
        self.track_step = deadband * track_step_ratio
        self.latched = None
        self.smoothed = None

    def filter(self, new_value):
        reading = self.median.filter(new_value)
        trend = self.long_median.filter(new_value)

        if self.latched is None:
            self.latched = reading
            self.smoothed = reading
            return self.latched

        # A deliberate, large move: track it immediately.
        if abs(reading - self.smoothed) >= self.big_jump:
            self.smoothed = reading
            self.latched = reading
            return self.latched

        drifting = abs(trend - self.latched) > self.drift_threshold

        if not drifting and abs(reading - self.latched) <= self.deadband:
            # Parked: hold the output, but keep the smoother near the reading so
            # a real move is picked up without delay.
            self.smoothed += 0.5 * (reading - self.smoothed)
            return self.latched

        # Tracking (or the reading finally left the deadband).
        alpha = self.fast_alpha if drifting else self.slow_alpha
        self.smoothed += alpha * (reading - self.smoothed)

        if abs(self.smoothed - self.latched) >= (self.track_step if drifting else self.deadband):
            self.latched = self.smoothed

        return self.latched


def median_then_ema(median_window=7, alpha=0.25):
    return lambda: MedianThenEMA(median_window, alpha)


def adaptive_slew(median_window=7, deadband=1.6, big_jump=8.0, **kwargs):
    return lambda: AdaptiveSlew(
        median_window=median_window, deadband=deadband, big_jump=big_jump, **kwargs
    )


CANDIDATES = [
    ("current (adaptive EMA + median5)", CurrentFilter),
    ("median5 + deadband/drift", adaptive_slew(median_window=5)),
    ("median5 + drift1.0", adaptive_slew(median_window=5, drift_threshold=1.0)),
    ("median5 + track0.25", adaptive_slew(median_window=5, track_step_ratio=0.25)),
    ("median5 + long15", adaptive_slew(median_window=5, long_window=15)),
    ("median5 + long35", adaptive_slew(median_window=5, long_window=35)),
    ("median7 + deadband/drift", adaptive_slew(median_window=7)),
    ("median7 + drift1.0", adaptive_slew(median_window=7, drift_threshold=1.0)),
    ("median9 + deadband/drift", adaptive_slew(median_window=9)),
]


def flick_stats(outputs, level=42.0):
    """A quick flick to a new value: how fast is the target reached?"""
    target = quantise(level)
    reached = None
    for offset, value in enumerate(outputs):
        if value == target:
            reached = offset + 1
            break
    return reached if reached is not None else "never"


def main():
    park = park_signal(200)
    step = step_signal()

    print("Model: parked slider at 27.0 with sigma=1.4 units, ~50 ms per sample")
    print("Raw input, quantised directly:")
    raw = [quantise(value) for value in park]
    print(f"  {jitter_stats(raw)}\n")

    print(f"{'filter':<36} {'jitter distinct/range/changes':<30} {'step lag':>12} {'overshoot':>10}")
    print("-" * 92)

    results = []
    for name, factory in CANDIDATES:
        parked = run(factory, park)
        move = run(factory, step)

        jit = jitter_stats(parked)
        st = step_stats(move)
        jitter_text = f"{jit['distinct']:>3} / {jit['range']:>3} / {jit['changes']:>4}"
        lag_text = f"{st['samples_to_90%']} (~{st['lag_ms']} ms)"
        print(f"{name:<36} {jitter_text:<30} {lag_text:>12} {st['overshoot']:>10}")
        results.append((name, jit, st))

    print("\nInterpretation")
    print("  distinct = different values the display took while parked (1 is ideal)")
    print("  range    = max-min while parked (0 is ideal; the report was ~2)")
    print("  changes  = how many times the value moved")
    print("  lag      = samples/time to react to a deliberate move (lower is better)")

    print("\n--- slow deliberate sweep (must not lag visibly) ---")
    rng = random.Random(7)
    sweep = [10 + index * 0.5 + rng.gauss(0, 1.4) for index in range(120)]
    for name, factory in CANDIDATES:
        outputs = run(factory, sweep)
        final = outputs[-1]
        ideal = quantise(sweep[-1])
        error = abs(final - ideal)
        print(f"  {name:<36} final={final:>3} ideal={ideal:>3} error={error}")

    print("\n--- quick flick (parked 27, then 5 samples moving to 42) ---")
    flick = []
    for index in range(30):
        if index < 10:
            flick.append(27.0 + rng.gauss(0, 1.4))
        else:
            flick.append(42.0 + rng.gauss(0, 1.4))
    for name, factory in CANDIDATES:
        outputs = run(factory, flick)
        samples = flick_stats(outputs[10:])
        print(f"  {name:<36} reached target after {samples} samples "
              f"(~{samples * SAMPLE_MS if isinstance(samples, int) else 0} ms)")

    print("\n--- parked jitter at a different level and noise (robustness) ---")
    for level, noise in ((5.0, 1.4), (50.0, 2.2), (95.0, 1.4)):
        park_n = park_signal(200, level=level, noise=noise, seed=int(level))
        for name, factory in CANDIDATES[:4]:
            outputs = run(factory, park_n)
            jit = jitter_stats(outputs)
            print(f"  level={level:>5} sigma={noise}  {name:<32} "
                  f"distinct={jit['distinct']} range={jit['range']} changes={jit['changes']}")
        print()


if __name__ == "__main__":
    main()
