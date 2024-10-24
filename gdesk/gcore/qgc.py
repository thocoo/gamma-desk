"""The Garbage Collector timer in the Qt Event Loop."""

import gc
import sys

from qtpy.QtCore import QObject, QTimer


class QGarbageCollector(QObject):
    """
    Disable automatic garbage collection and instead collect manually.

    Timeout every INTERVAL milliseconds.

    This is done to ensure that garbage collection only happens in the GUI
    thread, as otherwise Qt can crash.
    """

    INTERVAL = 5000

    def __init__(self, parent, debug=False):
        """QGarbageCollector."""
        QObject.__init__(self, parent)
        self.debug = debug

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)

        self.threshold = gc.get_threshold()

    def enable(self):
        """Enable the timer."""
        gc.disable()
        self.timer.start(self.INTERVAL)

    def disable(self):
        """Disable the timer."""
        self.timer.stop()
        gc.enable()

    def check(self):
        """Do the garbage collection."""
        cnt_0, cnt_1, cnt_2 = gc.get_count()
        if self.debug:
            sys.__stdout__.write('gc_check called: %d, %d, %d\n' % (cnt_0, cnt_1, cnt_2))
            sys.__stdout__.flush()

        if cnt_0 > self.threshold[0]:
            num = gc.collect(0)
            if self.debug:
                sys.__stdout__.write('collecting gen 0, found: %d unreachable\n' % num)
                sys.__stdout__.flush()
            if cnt_1 > self.threshold[1]:
                num = gc.collect(1)
                if self.debug:
                    sys.__stdout__.write('collecting gen 1, found: %d unreachable\n' % num)
                    sys.__stdout__.flush()
                if cnt_2 > self.threshold[2]:
                    num = gc.collect(2)
                    if self.debug:
                        sys.__stdout__.write('collecting gen 2, found: %d unreachable\n' % num)
                        sys.__stdout__.flush()
