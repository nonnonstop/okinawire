import struct
import time


class Lis3dh:
    I2C_ADDRESS = 0x19

    POWER_MODE_NORMAL = 0b00000000
    POWER_MODE_LOW = 0b00001000
    DATA_RATE_POWER_DOWN = 0b00000000
    DATA_RATE_1HZ = 0b00010000
    DATA_RATE_10HZ = 0b00100000
    DATA_RATE_25HZ = 0b00110000
    DATA_RATE_50HZ = 0b01000000
    DATA_RATE_100HZ = 0b01010000
    DATA_RATE_200HZ = 0b01100000
    DATA_RATE_400HZ = 0b01110000
    DATA_RATE_1600HZ_LOW = 0b10000000
    DATA_RATE_1250HZ_HIGH = 0b10010000
    DATA_RATE_5000HZ_LOW = 0b10010000

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

    def stop(self):
        if self._handle is not None:
            self._pi.i2c_close(self._handle)
            self._handle = None

    def apply_config(self, data_rate, power_mode):
        self._set_register(0x20, data_rate | power_mode | 0b111)

    def get_data(self):
        for _ in range(10):
            base_data = self._get_registers(0xa7, 7)
            status_reg, *data = struct.unpack('<Bhhh', base_data)
            if (status_reg & 0b00001000) == 0:
                time.sleep(0.01)
                continue
            return data
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
