import pigpio
from .error import IrError


class IrCodeAnalyzer:
    def __init__(self, time, err_rate):
        self._time = time
        self._err_rate = err_rate
        self._time_min = int(time * (1 - err_rate))
        self._time_max = int(time * (1 + err_rate))

    def _in_range(self, duration, length):
        return duration > self._time_min * length and duration < self._time_max * length


class IrCodeAnalyzerNec(IrCodeAnalyzer):
    def __init__(self, err_rate):
        super(IrCodeAnalyzerNec, self).__init__(562, err_rate)
        self._raw_data = [0, 0, 0, 0]

    def __str__(self):
        data = ', '.join(hex(d) for d in self._raw_data)
        return f'NEC: [{data}]'

    def _is_leader(self, code):
        return self._in_range(code[0], 16) and self._in_range(code[1], 8)

    def _is_data0(self, code):
        return self._in_range(code[0], 1) and self._in_range(code[1], 1)

    def _is_data1(self, code):
        return self._in_range(code[0], 1) and self._in_range(code[1], 3)

    def _is_repeat(self, code):
        return self._in_range(code[0], 16) and self._in_range(code[1], 4)

    def _is_end(self, code):
        return self._in_range(code[0], 1) and code[1] > self._time_min * 4

    def _is_repeat_end(self, code):
        return self._in_range(code[0], 1) and code[1] > self._time_min

    def analyze(self, codes):
        if not self._is_leader(codes[0]):
            return False
        codes.pop(0)
        self._raw_data = [0, 0, 0, 0]
        raw_data = self._raw_data
        for i in range(4):
            val = 0
            for j in range(8):
                code = codes.pop(0)
                if self._is_data1(code):
                    val ^= 1 << j
                elif not self._is_data0(code):
                    raise IrError(f'Unknown data code: {code}')
            raw_data[i] = val
        if (raw_data[2] ^ raw_data[3]) != 0xff:
            raise IrError(f'Broken data')
        code = codes.pop(0)
        if not self._is_end(code):
            raise IrError(f'Unknown end code: {code}')
        while codes:
            if not self._is_repeat(codes[0]):
                return True
            codes.pop(0)
            if not codes:
                raise IrError(f'No end code')
            code = codes.pop(0)
            if not self._is_repeat_end(code):
                raise IrError(f'Unknown repeat end code: {code}')
        return True


class IrCodeAnalyzerAeha(IrCodeAnalyzer):
    def __init__(self, err_rate):
        super(IrCodeAnalyzerAeha, self).__init__(425, err_rate)
        self._end_time_min = int(8000 * (1 - err_rate))
        self._raw_data = []

    def __str__(self):
        data = ', '.join(hex(d) for d in self._raw_data)
        return f'AEHA: [{data}]'

    def _is_leader(self, code):
        return self._in_range(code[0], 8) and self._in_range(code[1], 4)

    def _is_data0(self, code):
        return self._in_range(code[0], 1) and self._in_range(code[1], 1)

    def _is_data1(self, code):
        return self._in_range(code[0], 1) and self._in_range(code[1], 3)

    def _is_repeat(self, code):
        return self._in_range(code[0], 8) and self._in_range(code[1], 8)

    def _is_end(self, code):
        return self._in_range(code[0], 1) and code[1] >= self._end_time_min

    def _is_repeat_end(self, code):
        return self._in_range(code[0], 1) and code[1] >= self._time_min

    def analyze(self, codes):
        if not self._is_leader(codes[0]):
            return False
        codes.pop(0)
        self._raw_data = []
        raw_data = self._raw_data
        while True:
            val = 0
            for j in range(8):
                code = codes.pop(0)
                if j == 0 and self._is_end(code):
                    break
                elif self._is_data1(code):
                    val ^= 1 << j
                elif not self._is_data0(code):
                    raise IrError(f'Unknown data code: {code}')
            else:
                raw_data.append(val)
                continue
            break
        if len(raw_data) < 3:
            raise IrError(f'Too short data')
        if (((raw_data[0] ^ raw_data[1]) >> 4) ^ ((raw_data[0] ^ raw_data[1]) & 0xf)) != (raw_data[2] & 0xf):
            raise IrError(f'Broken customer code')
        while codes:
            if not self._is_repeat(codes[0]):
                return True
            codes.pop(0)
            if not codes:
                raise IrError(f'No end code')
            code = codes.pop(0)
            if not self._is_repeat_end(code):
                raise IrError(f'Unknown repeat end code: {code}')
        return True


class IrReceiver:
    _DURATION_MAX = 400

    def __init__(self, pi, gpio, handler, err_rate):
        self._pi = pi
        self._gpio = gpio
        self._cb = None  # for cancel callback
        self._last_tick = 0  # last tick of edge callback
        self._last_high_duration = 0  # last duration of high
        self._is_analyzing = False  # is analyzing input
        self._analyzing_codes = []  # codes currently analyzing
        self._handler = handler  # event handler
        self._analyzers = [
            IrCodeAnalyzerNec(err_rate),
            IrCodeAnalyzerAeha(err_rate),
        ]

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self):
        if self._cb:
            raise RuntimeError('IrReceiver already started')
        self._cb = self._pi.callback(
            self._gpio, pigpio.EITHER_EDGE, self._edge_callback)

    def stop(self):
        if self._cb is not None:
            self._cb.cancel()
            self._cb = None

    def _edge_callback(self, gpio, level, tick):
        last_tick = self._last_tick
        self._last_tick = tick
        if level == pigpio.TIMEOUT:
            self._is_analyzing = False
            self._pi.set_watchdog(gpio, 0)
            high_duration = self._last_high_duration
            if high_duration != 0:
                self._analyzing_codes.append(
                    (high_duration, self._DURATION_MAX * 1000))
                codes = self._analyzing_codes
                while codes:
                    try:
                        for analyzer in self._analyzers:
                            if analyzer.analyze(codes):
                                self._handler(analyzer)
                                break
                        else:
                            code = codes.pop(0)
                            raise IrError(f'Unknown leader: {code}')
                    except IrError as ex:
                        self._handler(ex)
                self._last_high_duration = 0
            return
        if not self._is_analyzing:
            self._is_analyzing = True
            self._pi.set_watchdog(gpio, self._DURATION_MAX)
            return
        if tick >= last_tick:
            duration = tick - last_tick
        else:
            duration = 4294967295 - last_tick + tick
        if level == pigpio.HIGH:
            self._last_high_duration = duration
        elif level == pigpio.LOW:
            self._analyzing_codes.append(
                (self._last_high_duration, duration))
            self._last_high_duration = 0
