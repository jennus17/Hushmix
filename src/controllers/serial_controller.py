"""Serial link to the Hushmix hardware mixer.

Protocol (9600 8N1), one packet per line::

    <volume>|<volume>|...-<button>|<button>|...

Changes made here:

* **The read loop no longer busy-polls.**  It used to ``time.sleep(0.01)`` and
  then poll ``in_waiting``, waking up 100 times per second forever; it now
  blocks in ``readline()`` with a timeout and reacts to ``\n`` or ``\r``.
* **Malformed packets are survivable.**  ``data_split[1]`` raised ``IndexError``
  whenever a line had no ``-`` separator; the handler then looped on the same
  condition.  Both halves are now parsed independently and defensively.
* **Reconnection is bounded.**  ``reconnect_serial`` recursed into itself, so a
  missing device produced unbounded recursion (and a poisoned serial thread).
  It is now an iterative retry with backoff and a companion watchdog thread.
* **A dead port no longer wedges the thread.**  A failed ``readline`` marks the
  port as broken, closes it and lets the watchdog retry.
"""

import threading
import time
from collections import deque

import pythoncom
import serial
import serial.tools.list_ports

from utils.logging_setup import get_logger

logger = get_logger("serial_controller")

DEFAULT_DEVICE_NAMES = ("USB-SERIAL CH340", "Dispositivo de Série USB")
DEFAULT_BAUD_RATE = 9600
DEFAULT_READ_TIMEOUT = 0.25
WATCHDOG_INTERVAL = 2.0
RECONNECT_MAX_DELAY = 30.0


class AdaptiveEMA:
    """Exponential moving average whose smoothing follows the delta size."""

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


class MedianFilter:
    """Median-of-window filter that works for any window size."""

    def __init__(self, window_size=5):
        self.window_size = max(1, window_size)
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


class FastCascadedFilter:
    """EMA followed by a median stage - cheap and good at removing jitter."""

    def __init__(self):
        self.filter1 = AdaptiveEMA()
        self.filter2 = MedianFilter(window_size=5)

    def filter(self, new_value):
        return self.filter2.filter(self.filter1.filter(new_value))

    def reset(self):
        self.filter1.reset()
        self.filter2.reset()


class SerialController:
    """Owns the serial port and pumps packets to the application callbacks."""

    def __init__(
        self,
        volume_callback,
        button_callback,
        connection_status_callback=None,
        device_names=None,
        baud_rate=DEFAULT_BAUD_RATE,
    ):
        self.volume_callback = volume_callback
        self.button_callback = button_callback
        self.connection_status_callback = connection_status_callback

        self.device_names = tuple(device_names or DEFAULT_DEVICE_NAMES)
        self.baud_rate = baud_rate

        self.arduino = None
        self._port_lock = threading.Lock()
        self.is_connected = False
        self._last_reported_status = None

        self.running = True
        self.volume_filters = []

        self._reader_thread = None
        self._watchdog_thread = None

        self._connect()
        self._start_threads()

    # ------------------------------------------------------------- connecting

    def get_com_port_by_device_name(self, device_name=None):
        """Return the COM port matching a USB-serial description, or ``None``."""
        names = (
            (device_name,)
            if device_name
            else self.device_names
        )
        try:
            ports = serial.tools.list_ports.comports()
        except Exception as error:
            logger.warning("Could not enumerate serial ports: %s", error)
            return None

        for port in ports:
            description = (port.description or "").lower()
            if any(name.lower() in description for name in names):
                return port.device
        return None

    def find_port(self):
        """Return the first matching port, falling back to any candidate."""
        port = self.get_com_port_by_device_name()
        if port:
            return port

        # Some CH340 clones report a generic description; accept the common
        # USB-serial prefixes as a secondary signal.
        try:
            for candidate in serial.tools.list_ports.comports():
                description = (candidate.description or "").lower()
                if any(
                    marker in description
                    for marker in ("ch340", "usb-serial", "usb serial", "arduino")
                ):
                    return candidate.device
        except Exception as error:
            logger.debug("Fallback port scan failed: %s", error)
        return None

    def _open_port(self, port):
        return serial.Serial(port, self.baud_rate, timeout=DEFAULT_READ_TIMEOUT)

    def _connect(self):
        """Try once to open the mixer; returns the port or ``None``."""
        port = self.find_port()
        if not port:
            logger.info("Mixer not found - check the USB connection")
            self._set_connected(False)
            return None

        with self._port_lock:
            if self.arduino and self.arduino.is_open:
                return self.arduino
            try:
                self.arduino = self._open_port(port)
                logger.info("Connected to mixer on %s", port)
                self._set_connected(True)
                return self.arduino
            except Exception as error:
                logger.warning("Could not open %s: %s", port, error)
                self.arduino = None
                self._set_connected(False)
                return None

    def initialize_serial(self, device_name=None, baud_rate=None):
        """Public entry point kept for backwards compatibility."""
        if baud_rate:
            self.baud_rate = baud_rate
        return self._connect()

    def reconnect_serial(self, max_attempts=None, device_name=None, baud_rate=None):
        """Iteratively reconnect with exponential backoff.

        Never recurses, and gives up after *max_attempts* (``None`` == retry
        until :attr:`running` becomes false, which the watchdog uses).
        """
        if not self.running:
            return None

        attempt = 0
        delay = 1.0
        while self.running and (max_attempts is None or attempt < max_attempts):
            attempt += 1
            self._close_port()

            result = self._connect()
            if result:
                return result

            time.sleep(min(delay, RECONNECT_MAX_DELAY))
            delay = min(delay * 1.5, RECONNECT_MAX_DELAY)

        return None

    def _close_port(self):
        with self._port_lock:
            if not self.arduino:
                return
            try:
                if self.arduino.is_open:
                    self.arduino.close()
            except Exception as error:
                logger.debug("Error closing serial port: %s", error)
            finally:
                self.arduino = None

    def _set_connected(self, connected):
        """Update the connection flag and notify the app only on change."""
        self.is_connected = bool(connected)
        if self._last_reported_status == self.is_connected:
            return
        self._last_reported_status = self.is_connected

        if self.connection_status_callback:
            try:
                self.connection_status_callback(self.is_connected)
            except Exception as error:
                logger.warning("Connection status callback failed: %s", error)

    # ------------------------------------------------------------------ threads

    def _start_threads(self):
        self._reader_thread = threading.Thread(
            target=self.read_serial_data, name="serial-reader", daemon=True
        )
        self._reader_thread.start()

        self._watchdog_thread = threading.Thread(
            target=self._connection_watchdog, name="serial-watchdog", daemon=True
        )
        self._watchdog_thread.start()

    def start_serial_thread(self):
        """Backwards compatible alias."""
        if self._reader_thread and self._reader_thread.is_alive():
            return
        self._start_threads()

    def _connection_watchdog(self):
        """Reconnect in the background so a missing device is not fatal."""
        delay = 1.0
        while self.running:
            time.sleep(delay)
            if not self.running:
                break
            if self.is_connected:
                delay = 1.0
                continue

            logger.debug("Mixer disconnected - attempting to reconnect")
            if self.reconnect_serial(max_attempts=1):
                delay = 1.0
            else:
                delay = min(delay * 1.5, RECONNECT_MAX_DELAY)

    def read_serial_data(self):
        """Read packets until :attr:`running` is cleared."""
        pythoncom.CoInitialize()
        try:
            while self.running:
                port = self.arduino
                if port is None or not port.is_open:
                    time.sleep(0.25)
                    continue

                try:
                    raw = port.readline()
                except (serial.SerialException, OSError) as error:
                    logger.warning("Serial read failed: %s", error)
                    self._close_port()
                    self._set_connected(False)
                    continue

                if not raw:
                    continue  # read timeout, nothing to do

                line = raw.decode("utf-8", errors="ignore").strip()
                if line:
                    self.handle_line(line)
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # pragma: no cover - defensive
                pass

    def handle_line(self, line):
        """Parse one packet and dispatch it (exposed for testing)."""
        volumes_part, separator, buttons_part = line.partition("-")

        if volumes_part:
            self.process_volume_data(volumes_part)

        if separator and buttons_part:
            self.process_button_data(buttons_part)

    # ------------------------------------------------------------- processing

    def _filter_for(self, index):
        while len(self.volume_filters) <= index:
            self.volume_filters.append(FastCascadedFilter())
        return self.volume_filters[index]

    def process_volume_data(self, data):
        """Convert and smooth the volume half of a packet."""
        smoothed = []
        for index, raw in enumerate(data.split("|")):
            raw = raw.strip()
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                logger.debug("Ignoring non-numeric volume %r", raw)
                continue

            smoothed.append(int(round(self._filter_for(index).filter(value))))

        if smoothed and self.volume_callback:
            self.volume_callback(smoothed)

    def process_button_data(self, data):
        """Convert and dispatch the button half of a packet."""
        states = []
        for raw in data.split("|"):
            raw = raw.strip()
            if not raw:
                continue
            try:
                states.append(int(float(raw)))
            except ValueError:
                logger.debug("Ignoring non-numeric button state %r", raw)

        if states and self.button_callback:
            self.button_callback(states)

    def get_connection_status(self):
        """Whether the mixer is currently connected."""
        return self.is_connected

    def cleanup(self):
        """Stop the threads and close the port (safe to call twice)."""
        logger.info("Cleaning up serial controller")
        self.running = False

        self._close_port()
        self._set_connected(False)

        reader = self._reader_thread
        if reader and reader.is_alive() and reader is not threading.current_thread():
            reader.join(timeout=1.0)

        watchdog = self._watchdog_thread
        if watchdog and watchdog.is_alive() and watchdog is not threading.current_thread():
            watchdog.join(timeout=1.0)

        logger.info("Serial controller cleanup completed")
