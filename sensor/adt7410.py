import struct
import time


class Adt7410:
    I2C_ADDRESS = 0x48

    def __init__(self, pi, bus):
        self._pi = pi
        self._bus = bus
        self._handle = None  # I2C handle

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self):
        if self._handle is not None:
            raise RuntimeError('Bme680 already started')
        self._handle = self._pi.i2c_open(self._bus, self.I2C_ADDRESS)
        try:
            self._set_register(0x03, 0b11100000)
        except:
            self.stop()
            raise

    def stop(self):
        if self._handle is not None:
            self._pi.i2c_close(self._handle)
            self._handle = None

    def get_data(self):
        self._set_register(0x03, 0b10100000)
        for _ in range(10):
            time.sleep(0.3)
            status = self._get_register(0x02)
            if (status & 0b10000000) != 0:
                continue
            base_data = self._get_registers(0x00, 2)
            data = struct.unpack('>h', base_data)
            return data[0] / 128
        raise RuntimeError('Failed to read')

    def _set_register(self, register, data):
        self._pi.i2c_write_byte_data(self._handle, register, data)

    def _get_register(self, register):
        return self._pi.i2c_read_byte_data(self._handle, register)

    def _get_registers(self, register, length):
        read, data = self._pi.i2c_read_i2c_block_data(self._handle, register, length)
        if read != length:
            raise RuntimeError(f"Failed to read: {read}")
        return data
