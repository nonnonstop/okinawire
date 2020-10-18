import ctypes
import struct
import time


class Bme680:
    I2C_ADDRESS = 0x77

    FILTER_0 = 0
    FILTER_1 = 1
    FILTER_3 = 2
    FILTER_7 = 3
    FILTER_15 = 4
    FILTER_31 = 5
    FILTER_63 = 6
    FILTER_127 = 7
    _FILTER_MASK = 0b00011100
    _FILTER_LIST = [
        0b00000000,
        0b00000100,
        0b00001000,
        0b00001100,
        0b00010000,
        0b00010100,
        0b00011000,
        0b00011100,
    ]

    OSRS_0 = 0
    OSRS_1 = 1
    OSRS_2 = 2
    OSRS_4 = 3
    OSRS_8 = 4
    OSRS_16 = 5
    _OSRS_T_MASK = 0b11100000
    _OSRS_T_LIST = [
        0b00000000,
        0b00100000,
        0b01000000,
        0b01100000,
        0b10000000,
        0b10100000,
    ]
    _OSRS_P_MASK = 0b00011100
    _OSRS_P_LIST = [
        0b00000000,
        0b00000100,
        0b00001000,
        0b00001100,
        0b00010000,
        0b00010100,
    ]
    _OSRS_H_MASK = 0b00000111
    _OSRS_H_LIST = [
        0b00000000,
        0b00000001,
        0b00000010,
        0b00000011,
        0b00000100,
        0b00000101,
    ]

    _MODE_MASK = 0b00000011
    MODE_SLEEP = 0b00000000
    MODE_FORCED = 0b00000001

    NB_CONVS_0 = 0
    NB_CONVS_1 = 1
    NB_CONVS_2 = 2
    NB_CONVS_3 = 3
    NB_CONVS_4 = 4
    NB_CONVS_5 = 5
    NB_CONVS_6 = 6
    NB_CONVS_7 = 7
    NB_CONVS_8 = 8
    NB_CONVS_9 = 9
    _NB_CONV_MASK = 0b00001111
    _NB_CONV_LIST = [
        0b00000000,
        0b00000001,
        0b00000010,
        0b00000011,
        0b00000100,
        0b00000101,
        0b00000110,
        0b00000111,
        0b00001000,
        0b00001001,
    ]

    _GAS_CONST_ARRAY1_INT = [
        2147483647,
        2147483647,
        2147483647,
        2147483647,
        2147483647,
        2126008810,
        2147483647,
        2130303777,
        2147483647,
        2147483647,
        2143188679,
        2136746228,
        2147483647,
        2126008810,
        2147483647,
        2147483647,
    ]
    _GAS_CONST_ARRAY2_INT = [
        4096000000,
        2048000000,
        1024000000,
        512000000,
        255744255,
        127110228,
        64000000,
        32258064,
        16016016,
        8000000,
        4000000,
        2000000,
        1000000,
        500000,
        250000,
        125000,
    ]

    def __init__(self, pi, bus):
        self._pi = pi
        self._bus = bus
        self._handle = None  # I2C handle
        self._par_t1 = None
        self._par_t2 = None
        self._par_t3 = None
        self._par_p1 = None
        self._par_p2 = None
        self._par_p3 = None
        self._par_p4 = None
        self._par_p5 = None
        self._par_p6 = None
        self._par_p7 = None
        self._par_p8 = None
        self._par_p9 = None
        self._par_p10 = None
        self._par_h1 = None
        self._par_h2 = None
        self._par_h3 = None
        self._par_h4 = None
        self._par_h5 = None
        self._par_h6 = None
        self._par_h7 = None
        self._par_g1 = None
        self._par_g2 = None
        self._par_g3 = None
        self.duration_ns = 1000000

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
            self._set_register(0xe0, 0xb6)
            time.sleep(0.01)
            self._assign_calibration_parameter()
        except:
            self.stop()
            raise

    def stop(self):
        if self._handle is not None:
            self._pi.i2c_close(self._handle)
            self._handle = None

    def _assign_calibration_parameter(self):
        data = self._get_registers(0x8a, 23)
        self._par_t2, self._par_t3, self._par_p1, self._par_p2, self._par_p3, self._par_p4, \
            self._par_p5, self._par_p7, self._par_p6, self._par_p8, self._par_p9, self._par_p10 \
            = struct.unpack('<hbxHhbxhhbbxxhhB', data)
        data = self._get_registers(0xe1, 14)
        self._par_h3, self._par_h4, self._par_h5, self._par_h6, self._par_h7, self._par_t1, \
            self._par_g2, self._par_g1, self._par_g3 = struct.unpack('<bbbBbHhbb', data[3:])
        self._par_h2 = (data[0] << 4) ^ (data[1] >> 4)
        self._par_h1 = (data[2] << 4) ^ (data[1] & 0xf)
        self._res_heat_val = self._get_register(0x00)
        self._res_heat_range = (self._get_register(0x02) & 0b00110000) >> 4
        self._range_switching_error = ctypes.c_byte(self._get_register(0x04)).value >> 4

    def apply_config(self, osrs_t, osrs_h, osrs_p, iir_filter, nb_conv, gas_wait, heat_temp, amb_temp):
        ctrl_gas1 = 0
        ctrl_gas1_mask = 0
        ctrl_hum = 0
        ctrl_hum_mask = 0
        ctrl_meas = 0
        ctrl_meas_mask = 0
        config = 0
        config_mask = 0
        duration_ns = 5793

        config ^= self._FILTER_LIST[iir_filter]
        config_mask ^= self._FILTER_MASK

        ctrl_meas ^= self._OSRS_T_LIST[osrs_t]
        ctrl_meas_mask ^= self._OSRS_T_MASK
        if osrs_t != 0:
            duration_ns += (2 ** (osrs_t - 1)) * 1963

        ctrl_meas ^= self._OSRS_P_LIST[osrs_p]
        ctrl_meas_mask ^= self._OSRS_P_MASK
        if osrs_p != 0:
            duration_ns += (2 ** (osrs_p - 1)) * 1963

        ctrl_hum ^= self._OSRS_H_LIST[osrs_h]
        ctrl_hum_mask ^= self._OSRS_H_MASK
        if osrs_h != 0:
            duration_ns += (2 ** (osrs_h - 1)) * 1963

        ctrl_gas1 ^= 0b00010000
        ctrl_gas1_mask ^= 0b00010000

        ctrl_gas1 ^= self._NB_CONV_LIST[nb_conv]
        ctrl_gas1_mask ^= self._NB_CONV_MASK

        self._set_registers(0x71, [ctrl_gas1, ctrl_hum], [ctrl_gas1_mask, ctrl_hum_mask])
        self._set_registers(0x74, [ctrl_meas, config], [ctrl_meas_mask, config_mask])

        duration_ns += gas_wait * 1000
        if gas_wait > 1008:
            gas_wait = 0b11000000 ^ (gas_wait >> 6)
        elif gas_wait > 252:
            gas_wait = 0b10000000 ^ (gas_wait >> 4)
        elif gas_wait > 63:
            gas_wait = 0b01000000 ^ (gas_wait >> 2)
        self._set_register(0x64 + nb_conv, gas_wait)

        var1 = (amb_temp * self._par_g3 // 1000) << 8
        var2 = (self._par_g1 + 784) * \
            (((self._par_g2 + 154009) * heat_temp * 5 // 100 + 3276800) // 10)
        var3 = var1 + (var2 >> 1)
        var4 = var3 // (self._res_heat_range + 4)
        var5 = 131 * self._res_heat_val + 65536
        res_heat_x100 = ((var4 // var5 - 250) * 34)
        res_heat = (res_heat_x100 + 50) // 100
        self._set_register(0x5a + nb_conv, res_heat)

        self._duration_secs = duration_ns / 1000000

    def set_mode(self, mode):
        self._set_register(0x74, mode, self._MODE_MASK)

    def get_data(self):
        self.set_mode(self.MODE_FORCED)
        time.sleep(self._duration_secs)

        for _ in range(10):
            meas_status_0, _, press_msb, press_lsb, press_xlsb, temp_msb, temp_lsb, temp_xlsb, \
                hum_msb, hum_lsb, _, _, _, gas_msb, gas_lsb = self._get_registers(0x1d, 15)

            if (meas_status_0 & 0b10000000) == 0:
                # if not new data
                time.sleep(0.01)
                continue
            if (gas_lsb & 0b00110000) == 0:
                # gas is unavailable
                time.sleep(0.01)
                continue

            temp_adc = (temp_msb << 12) ^ (temp_lsb << 4) ^ (temp_xlsb >> 4)
            var1 = (temp_adc >> 3) - (self._par_t1 << 1)
            var2 = (var1 * self._par_t2) >> 11
            var3 = (((var1 >> 1) * (var1 >> 1)) >> 12 * (self._par_t3 << 4)) >> 14
            t_fine = var2 + var3
            temp_comp = (t_fine * 5 + 128) >> 8

            hum_adc = (hum_msb << 8) ^ hum_lsb
            temp_scaled = temp_comp
            var1 = hum_adc - (self._par_h1 << 4) - ((temp_scaled * self._par_h3 // 100) >> 1)
            var2 = (self._par_h2 * ((temp_scaled * self._par_h4 // 100) +
                                    ((temp_scaled * temp_scaled * self._par_h5 // 100) >> 6) //
                                    100 + 16384)) >> 10
            var3 = var1 * var2
            var4 = ((self._par_h6 << 7) + (temp_scaled * self._par_h7 // 100)) >> 4
            var5 = ((var3 >> 14) * (var3 >> 14)) >> 10
            var6 = (var4 * var5) >> 1
            hum_comp = (((var3 + var6) >> 10) * 1000) >> 12

            press_adc = (press_msb << 12) ^ (press_lsb << 4) ^ (press_xlsb >> 4)
            var1 = (t_fine >> 1) - 64000
            var2 = ((((var1 >> 2) * (var1 >> 2)) >> 11) * self._par_p6) >> 2
            var2 = var2 + ((var1 * self._par_p5) << 1)
            var2 = (var2 >> 2) + (self._par_p4 << 16)
            var1 = (((((var1 >> 2) * (var1 >> 2)) >> 13) *
                     ((self._par_p3 << 5)) >> 3) + ((self._par_p2 * var1) >> 1))
            var1 = var1 >> 18
            var1 = ((32768 + var1) * self._par_p1) >> 15
            press_comp = 1048576 - press_adc
            press_comp = (press_comp - (var2 >> 12)) * 3125
            if press_comp >= 0x40000000:
                press_comp = (press_comp // var1) << 1
            else:
                press_comp = (press_comp << 1) // var1
            var1 = (self._par_p9 * (((press_comp >> 3) * (press_comp >> 3)) >> 13)) >> 12
            var2 = ((press_comp >> 2) * self._par_p8) >> 13
            var3 = ((press_comp >> 8) * (press_comp >> 8) * (press_comp >> 8) * self._par_p10) >> 17
            press_comp = press_comp + ((var1 + var2 + var3 + (self._par_p7 << 7)) >> 4)

            gas_adc = (gas_msb << 2) ^ (gas_lsb >> 6)
            gas_range = gas_lsb & 0b1111
            var1 = ((1340 + (5 * self._range_switching_error)) *
                    (self._GAS_CONST_ARRAY1_INT[gas_range])) >> 16
            var2 = (gas_adc << 15) - 16777216 + var1
            gas_res = (((self._GAS_CONST_ARRAY2_INT[gas_range] * var1) >> 9) + (var2 >> 1)) // var2

            return temp_comp / 100, hum_comp / 1000, press_comp / 100, gas_res

        raise RuntimeError('Failed to read')

    def _set_register(self, register, data, mask=None):
        if mask is None:
            self._pi.i2c_write_byte_data(self._handle, register, data)
            return
        base_data = self._get_register(register)
        new_data = (base_data & (~mask)) ^ data
        self._pi.i2c_write_byte_data(self._handle, register, new_data)

    def _set_registers(self, register, data, mask=None):
        if mask is None:
            new_data = []
            for data_item in data:
                new_data.append(register)
                new_data.append(data_item)
                register += 1
            self._pi.i2c_write_device(self._handle, new_data)
            return
        base_data = self._get_registers(register, len(data))
        new_data = []
        for base_item, data_item, mask_item in zip(base_data, data, mask):
            new_data.append(register)
            new_data.append((base_item & (~mask_item)) ^ data_item)
            register += 1
        self._pi.i2c_write_device(self._handle, new_data)

    def _get_register(self, register):
        return self._pi.i2c_read_byte_data(self._handle, register)

    def _get_registers(self, register, length):
        read, data = self._pi.i2c_read_i2c_block_data(
            self._handle, register, length)
        if read != length:
            raise RuntimeError(f"Failed to read: {read}")
        return data
