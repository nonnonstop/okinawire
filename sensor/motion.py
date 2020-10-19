import pigpio


class Motion:
    def __init__(self, pi, gpio, handler, duartion):
        self._pi = pi
        self._gpio = gpio
        self._duartion_ms = duartion * 1000
        self._cb = None  # for cancel callback
        self._last_level = False  # last level of edge callback
        self._handler = handler  # event handler

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self):
        if self._cb:
            raise RuntimeError('Motion sensor already started')
        self._pi.set_mode(self._gpio, pigpio.INPUT)
        self._cb = self._pi.callback(self._gpio, pigpio.EITHER_EDGE, self._on_output_changed)
        self._pi.set_watchdog(self._gpio, 0)

    def stop(self):
        self._pi.set_watchdog(self._gpio, 0)
        if self._cb is not None:
            self._cb.cancel()
            self._cb = None

    def _on_output_changed(self, gpio, level, tick):
        if level == pigpio.TIMEOUT:
            self._pi.set_watchdog(gpio, 0)
            self._last_level = False
            self._handler(False)
        elif level == pigpio.LOW:
            self._pi.set_watchdog(gpio, self._duartion_ms)
        elif self._last_level == False:
            self._last_level = True
            self._handler(True)
        else:
            self._pi.set_watchdog(gpio, 0)
