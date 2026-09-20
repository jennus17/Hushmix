"""Hand-off of work from background threads to the Tk main thread.

Tk is not thread-safe.  Volume changes only touch Core Audio, but button
actions create widgets, toggle mute state and synthesise keystrokes - doing
that from the serial reader thread can corrupt Tk's state or freeze the app
while ``pyautogui`` waits for an input queue.

:class:`DeferredActions` owns a bounded FIFO plus a periodic drain scheduled on
the Tk event loop.  Producers never block, consumers always run on the GUI
thread, and a burst of hardware events can never flood the event loop.
"""

import queue
import threading

from utils.logging_setup import get_logger

logger = get_logger("deferred_actions")


class DeferredActions:
    """Runs callables on the Tk main thread, in order.

    Parameters
    ----------
    root:
        The Tk root (or any widget) used to schedule the drain.
    interval_ms:
        How often the queue is drained.  Kept small so button presses feel
        instant while still batching a burst into one callback.
    max_pending:
        Queue capacity.  When full the *oldest* action is dropped, because a
        stale button press is worse than a missed one.
    """

    def __init__(self, root, interval_ms=15, max_pending=64):
        self.root = root
        self.interval_ms = interval_ms
        self._queue = queue.Queue(maxsize=max_pending)
        self._lock = threading.Lock()
        self._scheduled = False
        self._stopped = False

    def submit(self, function, *args, **kwargs):
        """Queue *function* for execution on the GUI thread.

        Returns ``True`` when the action was queued.
        """
        if self._stopped:
            return False

        item = (function, args, kwargs)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()  # drop the oldest action
                logger.debug("Action queue full - dropped the oldest entry")
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                logger.warning("Action queue still full - dropping %r", function)
                return False

        self._schedule()
        return True

    def _schedule(self):
        with self._lock:
            if self._scheduled or self._stopped:
                return
            self._scheduled = True
        try:
            self.root.after(self.interval_ms, self._drain)
        except Exception as error:
            # The window may be gone during shutdown; nothing to recover.
            with self._lock:
                self._scheduled = False
            logger.debug("Could not schedule action drain: %s", error)

    def _drain(self):
        with self._lock:
            self._scheduled = False

        if self._stopped:
            return

        processed = 0
        while processed < 16:
            try:
                function, args, kwargs = self._queue.get_nowait()
            except queue.Empty:
                break

            processed += 1
            try:
                function(*args, **kwargs)
            except Exception as error:
                logger.exception("Deferred action %r failed: %s", function, error)

        if not self._queue.empty():
            self._schedule()

    def stop(self):
        """Stop accepting and running queued actions."""
        self._stopped = True
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
