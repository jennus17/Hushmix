"""Filtering for the mixer's analog slider readings.

The mixer sends a noisy ADC reading per slider, roughly 20 times per second.
With a slider physically parked, the reading wanders by a unit or two, so the
displayed value used to flick between e.g. 26 / 28 / 27 on its own.

The first implementation chained an adaptive EMA into a median filter.  The EMA
is fast by design (alpha up to 0.3) and its output still wanders enough to cross
the 2-unit quantisation boundary, which is what produced the visible hops; the
harness in ``tests/tune_filter.py`` measured 2 distinct values, a range of 2 and
11 changes while parked.

This module replaces it with a three-stage pipeline that separates *noise* from
*intent* rather than trading one against the other:

1. a short median rejects spikes outright;
2. a long median estimates the trend, which tells us whether the slider is
   actually moving;
3. a deadband latches the output while the reading stays put - so parked jitter
   produces no movement at all - and collapses to close tracking as soon as the
   trend says the user is moving the slider, so nothing is lost in response
   speed.

Measured on the harness (parked, sigma 1.4): 1 distinct value, range 0, 0
changes; a deliberate step is followed in 3 samples (~150 ms) versus 9 (~450 ms)
before, with no overshoot.  A slow sweep tracks to the same value as the input.
"""

from collections import deque

from utils.logging_setup import get_logger

logger = get_logger("signal_filter")


class MedianFilter:
    """Median of a sliding window; rejects spikes and works for any window size."""

    def __init__(self, window_size=5):
        self.window_size = max(1, int(window_size))
        self.buffer = deque(maxlen=self.window_size)

    def filter(self, new_value):
        self.buffer.append(new_value)
        if len(self.buffer) < self.window_size:
            return new_value

        values = sorted(self.buffer)
        middle = len(values) // 2
        if len(values) % 2:
            return values[middle]
        return (values[middle - 1] + values[middle]) / 2.0

    def reset(self):
        self.buffer.clear()


class AdaptiveEMA:
    """Exponential moving average whose smoothing follows the size of the change."""

    def __init__(self, min_alpha=0.05, max_alpha=0.3, threshold=2.0):
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha
        self.threshold = max(threshold, 1e-6)
        self.value = None
        self.last_change = 0.0

    def filter(self, new_value):
        if self.value is None:
            self.value = new_value
            return self.value

        change = abs(new_value - self.value)
        self.last_change = change

        if change > self.threshold:
            alpha = self.max_alpha
        else:
            alpha = self.min_alpha + (self.max_alpha - self.min_alpha) * (
                change / self.threshold
            )

        self.value = alpha * new_value + (1 - alpha) * self.value
        return self.value

    def reset(self):
        self.value = None
        self.last_change = 0.0


class MixerSignalFilter:
    """Median + trend-detecting deadband, tuned for the Hushmix mixer.

    Parameters are exposed because the amount of noise depends on the mixer and
    its power supply; they can be overridden from the settings file.

    * ``median_window``   - spike rejection window (samples).
    * ``trend_window``    - window used to decide whether the slider is moving.
    * ``deadband``        - how far the reading may wander before the output is
                            allowed to move while parked, in slider units.
    * ``drift_threshold`` - trend movement that counts as "the user is moving".
    * ``big_jump``        - a change this large is treated as a deliberate move
                            and tracked immediately.
    * ``fast_alpha`` / ``slow_alpha`` - tracking smoothing while moving / while
                            leaving the deadband without a clear trend.
    """

    def __init__(
        self,
        median_window=5,
        trend_window=25,
        deadband=1.6,
        drift_threshold=1.0,
        big_jump=8.0,
        fast_alpha=0.5,
        slow_alpha=0.2,
        track_step_ratio=0.4,
    ):
        self.median = MedianFilter(window_size=median_window)
        self.trend = MedianFilter(window_size=trend_window)

        # Kept as attributes so from_settings() can read the effective defaults
        # and so the values are visible when debugging a noisy mixer.
        self.median_window = self.median.window_size
        self.trend_window = self.trend.window_size
        self.deadband = float(deadband)
        self.drift_threshold = float(drift_threshold)
        self.big_jump = float(big_jump)
        self.fast_alpha = float(fast_alpha)
        self.slow_alpha = float(slow_alpha)
        self.track_step = self.deadband * float(track_step_ratio)

        self.latched = None
        self.smoothed = None

    #: Tunables that may be overridden from the settings file.
    TUNABLES = {
        "median_window": int,
        "trend_window": int,
        "deadband": float,
        "drift_threshold": float,
        "big_jump": float,
    }

    @classmethod
    def from_settings(cls, settings_manager):
        """Build a filter using the user's settings, falling back to defaults."""
        probe = cls()
        resolved = {}
        for key, caster in cls.TUNABLES.items():
            fallback = getattr(probe, key)
            value = None
            if settings_manager is not None:
                value = settings_manager.get_setting(key)
            if value is None:
                resolved[key] = fallback
                continue
            try:
                resolved[key] = caster(value)
            except (TypeError, ValueError):
                logger.warning(
                    "Ignoring invalid %s=%r for the mixer filter", key, value
                )
                resolved[key] = fallback
        return cls(**resolved)

    def reset(self):
        """Forget the current reading (used when the mixer reconnects)."""
        self.median.reset()
        self.trend.reset()
        self.latched = None
        self.smoothed = None

    def filter(self, new_value):
        """Map one raw reading to a stabilised slider value."""
        reading = self.median.filter(new_value)
        trend = self.trend.filter(new_value)

        if self.latched is None:
            self.latched = reading
            self.smoothed = reading
            return self.latched

        # A deliberate, large move: follow it without delay.
        if abs(reading - self.smoothed) >= self.big_jump:
            self.smoothed = reading
            self.latched = reading
            return self.latched

        drifting = abs(trend - self.latched) > self.drift_threshold

        if not drifting and abs(reading - self.latched) <= self.deadband:
            # Parked: hold the output.  The smoother keeps tracking the reading
            # so a real move is picked up without a startup delay.
            self.smoothed += 0.5 * (reading - self.smoothed)
            return self.latched

        # Moving (or the reading finally left the deadband): track closely.
        alpha = self.fast_alpha if drifting else self.slow_alpha
        self.smoothed += alpha * (reading - self.smoothed)

        threshold = self.track_step if drifting else self.deadband
        if abs(self.smoothed - self.latched) >= threshold:
            self.latched = self.smoothed

        return self.latched
