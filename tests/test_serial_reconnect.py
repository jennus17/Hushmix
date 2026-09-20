"""Tests for the serial link's reconnect behaviour.

The reported bug: "when I disconnect the mixer for a long time, it doesn't
connect automatically, I have to restart the application."

There were two ways for the link to be lost without anyone noticing:

* **A silent port.** Unplugging a CH340 does not reliably make ``readline``
  raise. The handle stays open and every read times out, so the reader looped
  on ``b""``, the connection stayed flagged healthy, and the watchdog never
  retried - it only acted once the link was already known to be down.
* **A nameless port.** The mixer was located purely by matching the USB serial
  *description*, so a device that came back with an empty or altered
  description could never be found again.

Both are covered here, along with the risks the fixes introduce: the identity
probe must not claim an unrelated port, and silence must not tear down a link
that is merely quiet.

Run with::

    python tests/test_serial_reconnect.py
"""

import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

FAILURES = []
CHECKS = [0]


def check(condition, message):
    CHECKS[0] += 1
    if condition:
        print(f"ok   {message}")
    else:
        FAILURES.append(message)
        print(f"FAIL {message}")


def section(name):
    print(f"\n== {name} ==")


# --------------------------------------------------------------- fake pyserial

STATE = {}


class FakeSerialException(OSError):
    pass


class FakePort:
    """One serial port whose behaviour the scenario controls."""

    def __init__(self, device, description="USB-SERIAL CH340", hwid="USB VID_1A86&PID_7523"):
        self.device = device
        self.description = description
        self.hwid = hwid
        #: "mixer"  - streams valid packets
        #: "silent" - opens, but never says anything
        #: "garbage"- opens, and says something that is not a packet
        self.behaviour = "mixer"
        #: Set when the device is unplugged.  An open handle to a removed
        #: device stops delivering and usually stops raising too.
        self.gone = False


class FakeSerial:
    def __init__(self, device, baudrate, timeout=None):
        STATE["opens"].append(device)
        self.port = next((p for p in STATE["all_ports"] if p.device == device), None)
        if self.port is None or self.port.gone:
            raise FakeSerialException(f"could not open port {device}")
        self.device = device
        self.timeout = timeout
        self.is_open = True
        self._closed = False
        self._lines = 0

    def readline(self):
        if self._closed:
            raise FakeSerialException("port is closed")

        if self.port.gone:
            if self.port.behaviour == "raise":
                self.is_open = False
                raise FakeSerialException("ClearCommError failed (device not connected)")
            # The handle survives the device; reads just time out forever.
            time.sleep(min(self.timeout or 0.05, 0.05))
            return b""

        behaviour = self.port.behaviour
        time.sleep(min(self.timeout or 0.05, 0.05))

        if behaviour == "mixer":
            self._lines += 1
            return b"50|60|70-1|0|2\r\n"
        if behaviour == "garbage":
            self._lines += 1
            return b"<<< not a mixer >>>\r\n"
        return b""

    def close(self):
        STATE["closes"].append(self.device)
        self._closed = True
        self.is_open = False


def install_fake_serial():
    serial = types.ModuleType("serial")
    serial.Serial = FakeSerial
    serial.SerialException = FakeSerialException

    tools = types.ModuleType("serial.tools")
    list_ports = types.ModuleType("serial.tools.list_ports")
    list_ports.comports = lambda *a, **k: list(STATE["ports"])
    tools.list_ports = list_ports
    serial.tools = tools
    serial.__path__ = []
    sys.modules["serial"] = serial
    sys.modules["serial.tools"] = tools
    sys.modules["serial.tools.list_ports"] = list_ports

    pythoncom = sys.modules.get("pythoncom") or types.ModuleType("pythoncom")
    pythoncom.CoInitialize = lambda: None
    pythoncom.CoUninitialize = lambda: None
    sys.modules["pythoncom"] = pythoncom


install_fake_serial()

import controllers.serial_controller as serial_module  # noqa: E402
from controllers.serial_controller import SerialController  # noqa: E402


def make_controller(silence_timeout=0.3):
    """A real controller (with its threads) against the fake ports."""
    STATE.setdefault("opens", [])
    STATE.setdefault("closes", [])
    events = []
    stamps = []
    volumes = []
    buttons = []
    controller = SerialController(
        volume_callback=volumes.append,
        button_callback=buttons.append,
        connection_status_callback=lambda connected: (
            events.append(connected),
            stamps.append(time.monotonic()),
        ),
        silence_timeout=silence_timeout,
    )
    controller._test_events = events
    controller._test_stamps = stamps
    controller._test_volumes = volumes
    controller._test_buttons = buttons
    return controller


def wait_for(predicate, timeout, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def scenario(ports):
    """Start a scenario with *ports* enumerated; all of them are present."""
    for port in ports:
        port.gone = False
    STATE["all_ports"] = list(ports)
    STATE["ports"] = list(ports)
    STATE["opens"] = []
    STATE["closes"] = []


def unplug(mode="silent"):
    """Remove every device: nothing enumerates, open handles go dead."""
    for port in STATE["all_ports"]:
        port.gone = True
        # How the open handle behaves once the device is gone.
        port.behaviour = "raise" if mode == "raise" else "silent"
    STATE["ports"] = []


def replug(ports):
    """Re-attach devices, which may be on different ports with new identities."""
    for port in ports:
        port.gone = False
    STATE["all_ports"] = list(ports)
    STATE["ports"] = list(ports)


def main():
    # Timings compressed so the suite finishes quickly.  The controller takes
    # its silence timeout as an argument; these two are module level.
    serial_module.WATCHDOG_INTERVAL = 0.05
    serial_module.HEALTH_CHECK_INTERVAL = 0.05
    serial_module.RECONNECT_MAX_DELAY = 0.2

    # ---------------------------------------------------------- packet shape
    section("packet detection (the probe's test)")

    check(
        SerialController.looks_like_packet("50|60|70-1|0|2"),
        "a well-formed packet is recognised",
    )
    check(
        SerialController.looks_like_packet("10|20-0"),
        "a packet with one button is recognised",
    )
    for bad in ("", "<<< not a mixer >>>", "hello", "50|60|70", "-1|0", "5 0-1|0"):
        check(
            not SerialController.looks_like_packet(bad),
            f"{bad!r} is rejected",
        )

    # ------------------------------------------------------------ the probe
    section("identity probe")

    scenario([FakePort("COM9", description="", hwid="")])
    STATE["ports"][0].behaviour = "garbage"
    controller = SerialController.__new__(SerialController)
    controller.baud_rate = 9600
    check(
        not controller._port_answers_as_mixer("COM9"),
        "a port that talks nonsense is not mistaken for the mixer",
    )

    STATE["ports"][0].behaviour = "silent"
    check(
        not controller._port_answers_as_mixer("COM9"),
        "a silent port is not mistaken for the mixer",
    )

    STATE["ports"][0].behaviour = "mixer"
    check(
        controller._port_answers_as_mixer("COM9"),
        "a streaming port is recognised as the mixer",
    )

    # --------------------------------------------------- silent port recovery
    section("unplugged with no error (the reported bug)")

    scenario([FakePort("COM4")])
    controller = make_controller()
    try:
        check(
            wait_for(lambda: controller.get_connection_status(), 2.0),
            "connected at startup",
        )

        # The device vanishes but reads keep timing out instead of raising.
        unplug("silent")
        check(
            wait_for(lambda: not controller.get_connection_status(), 3.0),
            "silence is noticed and the link is reported down",
        )
    finally:
        controller.cleanup()

    # The same, but the port list empties as well.
    scenario([FakePort("COM4")])
    controller = make_controller()
    try:
        wait_for(lambda: controller.get_connection_status(), 2.0)
        unplug("raise")
        check(
            wait_for(lambda: not controller.get_connection_status(), 3.0),
            "a port that disappears is reported down",
        )
    finally:
        controller.cleanup()

    # -------------------------------------------------- nameless port recovery
    section("plugged back in with no description")

    scenario([FakePort("COM4")])
    controller = make_controller()
    try:
        check(
            wait_for(lambda: controller.get_connection_status(), 2.0),
            "connected at startup",
        )

        unplug("raise")
        check(
            wait_for(lambda: not controller.get_connection_status(), 3.0),
            "reported down while unplugged",
        )

        # ...and back, on another port, with nothing to identify it by.
        replug([FakePort("COM7", description="", hwid="")])
        check(
            wait_for(lambda: controller.get_connection_status(), 6.0),
            "found again through the identity probe despite no description",
        )
    finally:
        controller.cleanup()

    # ------------------------------------------------ same port, back again
    section("plugged back in on the same port")

    scenario([FakePort("COM4")])
    controller = make_controller()
    try:
        wait_for(lambda: controller.get_connection_status(), 2.0)

        unplug("raise")
        wait_for(lambda: not controller.get_connection_status(), 3.0)

        replug([FakePort("COM4")])
        check(
            wait_for(lambda: controller.get_connection_status(), 6.0),
            "reconnected on the port that worked before",
        )
        check(
            controller._test_events == [True, False, True],
            f"the app saw exactly one down and one up: {controller._test_events}",
        )
    finally:
        controller.cleanup()

    # ----------------------------------------------------- a settling link
    section("reconnecting does not spin")

    # The real mixer streams at ~25 packets/s with a worst gap of 66 ms, so a
    # silent-but-present device is a dead link rather than an idle one.  What
    # matters is that the retry loop is paced by the silence timeout instead of
    # spinning: with the timings compressed 20x here, a cycle must still take a
    # meaningful fraction of a second.
    scenario([FakePort("COM4")])
    STATE["all_ports"][0].behaviour = "silent"   # present, never sends
    controller = make_controller(silence_timeout=0.3)
    try:
        wait_for(lambda: len(controller._test_events) >= 2, 3.0)
        time.sleep(1.2)

        # Measure between cycle *starts* (each "connected" event), not between
        # every event: a cycle always contains a connect/disconnect pair, and
        # those two are adjacent by construction.
        events = controller._test_events
        starts = [
            controller._test_stamps[index]
            for index, connected in enumerate(events)
            if connected
        ]
        gaps = [
            starts[index] - starts[index - 1]
            for index in range(1, len(starts))
        ]
        shortest = min(gaps) if gaps else 0.0
        check(
            len(gaps) >= 1 and shortest >= 0.2,
            f"cycles are paced by the silence timeout, not spinning "
            f"(shortest cycle {shortest * 1000:.0f} ms over {len(starts)} connects)",
        )
        check(
            controller._reader_thread.is_alive()
            and controller._watchdog_thread.is_alive(),
            "both threads are still alive after repeated failed reconnects",
        )
    finally:
        controller.cleanup()

    # ------------------------------------------- a healthy link keeps working
    section("a healthy link still delivers")

    scenario([FakePort("COM4")])
    controller = make_controller(silence_timeout=5.0)
    try:
        check(
            wait_for(lambda: controller._test_volumes, 3.0),
            "volume packets reach the callback",
        )
        check(
            wait_for(lambda: controller._test_buttons, 3.0),
            "button packets reach the callback",
        )
        check(
            controller.get_connection_status(),
            "and the link stays connected",
        )
    finally:
        controller.cleanup()

    # -------------------------------------------------- the probe is not noisy
    section("the probe does not disturb the application")

    scenario([FakePort("COM4", description="", hwid="")])
    controller = make_controller()
    try:
        wait_for(lambda: controller.get_connection_status(), 4.0)
        # Packet data must arrive once, from the real connection - not once per
        # probe attempt as well.
        settled = len(controller._test_volumes)
        time.sleep(0.4)
        growth = len(controller._test_volumes) - settled
        check(
            growth < 40,
            f"probes are not feeding the volume callback (grew by {growth})",
        )
    finally:
        controller.cleanup()

    print("\n" + "=" * 60)
    print(f"checks passed: {CHECKS[0] - len(FAILURES)}")
    print(f"failures     : {len(FAILURES)}")
    for failure in FAILURES:
        print(f"  - {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.exit(code)
