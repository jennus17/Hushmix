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
* **A silent port is detected.**  Unplugging does not always make ``readline``
  raise: on Windows the handle can stay "open" and the read just times out
  forever, so the reader looped happily on ``b""`` and the connection stayed
  flagged as healthy - which also stopped the watchdog from retrying, because
  the watchdog only helped when the connection was already known to be down.
  The link is now judged by traffic: no packet for :data:`SILENCE_TIMEOUT`
  seconds closes the port and lets the watchdog reconnect.  This was the
  "unplugged for a long time and it never comes back" report.
* **The mixer is found again even when its description changes.**  The port was
  located purely by matching the USB serial *description*, so a CH340 that
  came back with an empty or altered description was never found again and the
  application had to be restarted.  The port number that worked last is now
  reused, and the USB VID/PID is remembered as a fallback.
* **A failed scan says what it saw.**  "Mixer not found" logged nothing about
  the ports that were present, so there was no way to tell a genuinely absent
  device from a matching failure.
"""

import re
import threading
import time

import pythoncom
import serial
import serial.tools.list_ports

from utils.logging_setup import get_logger

#: Re-exported for backwards compatibility; the implementations now live in
#: :mod:`utils.signal_filter` so they can be exercised without pyserial.
from utils.signal_filter import AdaptiveEMA, MedianFilter  # noqa: F401

logger = get_logger("serial_controller")

DEFAULT_DEVICE_NAMES = ("USB-SERIAL CH340", "Dispositivo de Série USB")
DEFAULT_BAUD_RATE = 9600
DEFAULT_READ_TIMEOUT = 0.25
#: How often the watchdog thread wakes (seconds).  Short, because this is what
#: notices a cable that was pulled without producing an error.
WATCHDOG_INTERVAL = 0.5
#: How often the link's health is actually judged, within those wakes.
HEALTH_CHECK_INTERVAL = 1.0
RECONNECT_MAX_DELAY = 30.0
#: Close and re-open the port after this many seconds without a packet.  The
#: mixer streams at about 25 packets per second with a worst observed gap of
#: 66 ms (measured on the real hardware), so silence means the link is gone.
#: The margin is deliberate: a busy machine can stall a thread for a moment, but
#: not for a hundred times the normal gap.
SILENCE_TIMEOUT = 10.0
#: USB vendor IDs of serial chips the mixer is built on.  Used only when the
#: description cannot identify the port.
KNOWN_VENDOR_IDS = ("1A86", "2341", "1B4F", "10C4", "0403")
#: How long to listen on a candidate port to decide whether the mixer is behind
#: it, and how many lines to look at.  The mixer streams, so a correct port
#: answers almost immediately.
PROBE_SECONDS = 0.35
PROBE_MAX_LINES = 8

_VID_PID_PATTERN = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")


class FastCascadedFilter:
    """Deprecated: the previous EMA + median chain (kept for callers/tests)."""

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
        settings_manager=None,
        silence_timeout=SILENCE_TIMEOUT,
    ):
        self.volume_callback = volume_callback
        self.button_callback = button_callback
        self.connection_status_callback = connection_status_callback

        self.device_names = tuple(device_names or DEFAULT_DEVICE_NAMES)
        self.baud_rate = baud_rate
        self.silence_timeout = silence_timeout

        self.arduino = None
        self._port_lock = threading.Lock()
        self.is_connected = False
        self._last_reported_status = None

        self.running = True
        self.volume_filters = []
        self._filter_settings = settings_manager

        #: Port that worked last, and the USB identity behind it.  A CH340 that
        #: comes back on another port number, or with its description missing,
        #: is still recognised through these.
        self._last_known_port = None
        self._known_signature = None
        #: When a packet last arrived.  ``None`` means "not connected yet".
        self._last_packet_at = None
        self._reconnect_reported = False

        self._reader_thread = None
        self._watchdog_thread = None

        self._connect()
        self._start_threads()

    # ------------------------------------------------------------- connecting

    def _port_signature(self, port_info):
        """USB VID/PID of a port, or ``None`` when it cannot be determined."""
        hardware_id = getattr(port_info, "hwid", None) or ""
        match = _VID_PID_PATTERN.search(hardware_id)
        if match:
            return match.group(0).upper()

        vid = getattr(port_info, "vid", None)
        pid = getattr(port_info, "pid", None)
        if vid is not None and pid is not None:
            return f"VID_{vid:04X}&PID_{pid:04X}"
        return None

    def _describe_port(self, port_info):
        """A port as one readable line, for the "what did you see" log."""
        signature = self._port_signature(port_info)
        description = getattr(port_info, "description", "") or "no description"
        return (
            f"{getattr(port_info, 'device', '?')} [{description}]"
            f"{' ' + signature if signature else ''}"
        )

    def get_com_port_by_device_name(self, device_name=None):
        """Return the COM port matching a USB-serial description, or ``None``."""
        names = (device_name,) if device_name else self.device_names
        for port in self._enumerate_ports():
            description = (port.description or "").lower()
            if any(name.lower() in description for name in names):
                return port.device
        return None

    def _enumerate_ports(self):
        """Every serial port, or an empty list when enumeration itself fails."""
        try:
            return list(serial.tools.list_ports.comports())
        except Exception as error:
            logger.warning("Could not enumerate serial ports: %s", error)
            return []

    def find_port(self):
        """Return the mixer's port as ``(device, signature)``, or ``(None, None)``.

        Order matters.  The port that worked last is trusted first, because a
        device that re-enumerated can come back on a different COM number or
        with a generic description; the USB identity is checked next; the
        description match is the fallback for a first connection.
        """
        ports = self._enumerate_ports()

        def result(port_info):
            return port_info.device, self._port_signature(port_info)

        # 1. Same port number as last time, if anything is there now.
        if self._last_known_port:
            for port in ports:
                if port.device == self._last_known_port:
                    return result(port)

        # 2. Same USB device, wherever Windows put it.
        if self._known_signature:
            for port in ports:
                if self._port_signature(port) == self._known_signature:
                    return result(port)

        # 3. What the device calls itself.
        named = self.get_com_port_by_device_name()
        if named:
            for port in ports:
                if port.device == named:
                    return result(port)
            return named, None

        # 4. A CH340 clone with a generic description or an empty one.
        for candidate in ports:
            description = (candidate.description or "").lower()
            if any(
                marker in description
                for marker in ("ch340", "usb-serial", "usb serial", "arduino")
            ):
                return result(candidate)

            signature = self._port_signature(candidate)
            if signature and signature[4:8] in KNOWN_VENDOR_IDS:
                return result(candidate)

        # 5. Ask the ports.  A CH340 that re-enumerated can come back with no
        #    description *and* no hardware id, which leaves nothing to match
        #    on - this is what made a long unplug unrecoverable.  The mixer
        #    streams packets, so the device that answers is the mixer.
        for candidate in ports:
            if self._port_answers_as_mixer(candidate.device):
                return result(candidate)

        self._log_scan_result(ports)
        return None, None

    def _port_answers_as_mixer(self, device):
        """True when *device* delivers something that parses as a mixer packet.

        Deliberately does not touch :attr:`arduino` or the callbacks: this is a
        question asked of a stranger port, and the answer must not be reported
        to the application as a volume or a button press.
        """
        try:
            handle = serial.Serial(device, self.baud_rate, timeout=0.05)
        except Exception as error:
            logger.debug("Probe: %s is not usable (%s)", device, error)
            return False

        try:
            deadline = time.monotonic() + PROBE_SECONDS
            for _ in range(PROBE_MAX_LINES):
                if time.monotonic() >= deadline:
                    break
                raw = handle.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if self.looks_like_packet(line):
                    logger.info("Probe: %s answers like the mixer", device)
                    return True
        except Exception as error:
            logger.debug("Probe: %s failed while reading (%s)", device, error)
        finally:
            try:
                handle.close()
            except Exception as error:
                logger.debug("Probe: could not close %s (%s)", device, error)

        return False

    @staticmethod
    def looks_like_packet(line):
        """Whether a line has the shape of a mixer packet.

        Used by the port probe, and by nothing else: the live read path still
        hands every line to :meth:`handle_line`, which is deliberately lenient.
        """
        if not line or "-" not in line:
            return False
        volumes_part, _, buttons_part = line.partition("-")
        if not volumes_part or not buttons_part:
            return False

        def all_numeric(part):
            fields = [field.strip() for field in part.split("|")]
            fields = [field for field in fields if field]
            if not fields:
                return False
            for field in fields:
                try:
                    float(field)
                except ValueError:
                    return False
            return True

        return all_numeric(volumes_part) and all_numeric(buttons_part)

    def _log_scan_result(self, ports):
        """Say what the scan saw, but only when it changes."""
        summary = ", ".join(self._describe_port(port) for port in ports) or "none"
        if summary == getattr(self, "_last_scan_summary", None):
            return
        self._last_scan_summary = summary
        if ports:
            logger.info(
                "No mixer among %d serial port(s): %s", len(ports), summary
            )
        else:
            logger.info("No serial ports present at all")

    def _open_port(self, port):
        return serial.Serial(port, self.baud_rate, timeout=DEFAULT_READ_TIMEOUT)

    def _connect(self):
        """Try once to open the mixer; returns the port or ``None``.

        Everything that can block or enumerate - locating the port, reading its
        USB identity, opening it - happens outside :attr:`_port_lock`.  Holding
        that lock across the open call also blocked ``_close_port`` from the
        reader thread, which is what left a dead handle behind.
        """
        port, signature = self.find_port()
        if not port:
            logger.info("Mixer not found - check the USB connection")
            self._set_connected(False)
            return None

        with self._port_lock:
            if self.arduino and self.arduino.is_open:
                return self.arduino

        try:
            handle = self._open_port(port)
        except Exception as error:
            logger.warning("Could not open %s: %s", port, error)
            with self._port_lock:
                self.arduino = None
            self._set_connected(False)
            return None

        with self._port_lock:
            self.arduino = handle

        self._last_known_port = port
        if signature:
            self._known_signature = signature
        self._last_packet_at = time.monotonic()
        self._reconnect_reported = False

        logger.info("Connected to mixer on %s", port)
        # Start from a clean signal history after a reconnect.
        self.reset_filters()
        self._set_connected(True)
        return handle

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

    def seconds_since_packet(self):
        """How long the link has been silent, or ``None`` if never connected."""
        if self._last_packet_at is None:
            return None
        return time.monotonic() - self._last_packet_at

    def _note_activity(self):
        self._last_packet_at = time.monotonic()

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

    def _check_link_health(self):
        """Downgrade a silent link to "disconnected" so it gets reopened.

        Unplugging a CH340 does not reliably make ``readline`` raise: the handle
        often stays open and every read simply times out.  Without this the
        application believed it was connected, the banner stayed hidden and the
        watchdog never retried - the mixer only came back after a restart.

        Only a link that has actually carried a packet is judged, so a mixer
        that is still starting up is not torn down immediately.  Note the
        deliberate absence of an ``is_connected`` guard: the handle can survive
        the device, and a silently dead link is exactly the case this exists to
        catch, even though nothing has flagged it as down yet.
        """
        if self.arduino is None:
            return

        silence = self.seconds_since_packet()
        if silence is None or silence < self.silence_timeout:
            return

        logger.warning(
            "No data from the mixer for %.1fs - reopening the port", silence
        )
        self._close_port()
        self._last_packet_at = None
        self._set_connected(False)

    def _connection_watchdog(self):
        """Reconnect in the background so a missing device is not fatal."""
        delay = 1.0
        last_health_check = 0.0

        while self.running:
            time.sleep(WATCHDOG_INTERVAL)
            if not self.running:
                break

            now = time.monotonic()
            if now - last_health_check >= HEALTH_CHECK_INTERVAL:
                last_health_check = now
                self._check_link_health()

            if now < getattr(self, "_next_reconnect_at", 0.0):
                continue

            if self.is_connected:
                delay = 1.0
                self._next_reconnect_at = 0.0
                continue

            if not self._reconnect_reported:
                self._reconnect_reported = True
                logger.info("Mixer disconnected - attempting to reconnect")

            if self.reconnect_serial(max_attempts=1):
                delay = 1.0
                self._next_reconnect_at = 0.0
            else:
                delay = min(delay * 1.5, RECONNECT_MAX_DELAY)
                self._next_reconnect_at = time.monotonic() + delay

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
                except Exception as error:
                    # Deliberately broad.  Closing the port from the watchdog
                    # while this thread is blocked inside pyserial does not
                    # raise SerialException: on Windows the handle and the
                    # overlapped structure are released underneath the read, so
                    # the call fails with anything from OSError to a TypeError
                    # from deep inside ctypes.  Catching only SerialException
                    # let that kill the reader thread outright, and a dead
                    # reader is never noticed by anything else - which is why
                    # the mixer could stop responding until a restart.
                    logger.warning(
                        "Serial read failed (%s): %s", type(error).__name__, error
                    )
                    self._close_port()
                    self._set_connected(False)
                    self._last_packet_at = None
                    continue

                if not raw:
                    # A read timeout.  Silence is judged by the watchdog, not
                    # here, so a healthy but quiet device is not torn down by
                    # an unlucky run of timeouts.
                    continue

                self._note_activity()

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
            from utils.signal_filter import MixerSignalFilter

            self.volume_filters.append(
                MixerSignalFilter.from_settings(self._filter_settings)
            )
        return self.volume_filters[index]

    def reset_filters(self):
        """Drop the filter state (called when the mixer reconnects).

        Without this a reconnect would keep the previous latched values and the
        first packet after reconnecting could be ignored as "parked".
        """
        for volume_filter in self.volume_filters:
            volume_filter.reset()

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
