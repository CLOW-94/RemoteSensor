from machine import I2C
import time

# BMP280 default address
BMP280_I2CADDR = 0x76

# Operating modes / oversampling
BMP280_OSAMPLE_1 = 1
BMP280_OSAMPLE_2 = 2
BMP280_OSAMPLE_4 = 3
BMP280_OSAMPLE_8 = 4
BMP280_OSAMPLE_16 = 5

# Registers
BMP280_REGISTER_DIG_T1 = 0x88
BMP280_REGISTER_DIG_T2 = 0x8A
BMP280_REGISTER_DIG_T3 = 0x8C

BMP280_REGISTER_DIG_P1 = 0x8E
BMP280_REGISTER_DIG_P2 = 0x90
BMP280_REGISTER_DIG_P3 = 0x92
BMP280_REGISTER_DIG_P4 = 0x94
BMP280_REGISTER_DIG_P5 = 0x96
BMP280_REGISTER_DIG_P6 = 0x98
BMP280_REGISTER_DIG_P7 = 0x9A
BMP280_REGISTER_DIG_P8 = 0x9C
BMP280_REGISTER_DIG_P9 = 0x9E

BMP280_REGISTER_CHIPID = 0xD0
BMP280_REGISTER_RESET = 0xE0
BMP280_REGISTER_STATUS = 0xF3
BMP280_REGISTER_CONTROL = 0xF4
BMP280_REGISTER_CONFIG = 0xF5
BMP280_REGISTER_PRESSURE_DATA = 0xF7
BMP280_REGISTER_TEMP_DATA = 0xFA


class Device:
    def __init__(self, address, i2c):
        self._address = address
        self._i2c = i2c

    def write8(self, register, value):
        b = bytearray(1)
        b[0] = value & 0xFF
        self._i2c.writeto_mem(self._address, register, b)

    def readU8(self, register):
        return int.from_bytes(
            self._i2c.readfrom_mem(self._address, register, 1), "little"
        ) & 0xFF

    def readS8(self, register):
        result = self.readU8(register)
        if result > 127:
            result -= 256
        return result

    def readU16(self, register, little_endian=True):
        result = int.from_bytes(
            self._i2c.readfrom_mem(self._address, register, 2), "little"
        ) & 0xFFFF
        if not little_endian:
            result = ((result << 8) & 0xFF00) + (result >> 8)
        return result

    def readS16(self, register, little_endian=True):
        result = self.readU16(register, little_endian)
        if result > 32767:
            result -= 65536
        return result

    def readU16LE(self, register):
        return self.readU16(register, little_endian=True)

    def readS16LE(self, register):
        return self.readS16(register, little_endian=True)


class BMP280:
    def __init__(self, mode=BMP280_OSAMPLE_1, address=BMP280_I2CADDR, i2c=None):
        if mode not in [
            BMP280_OSAMPLE_1,
            BMP280_OSAMPLE_2,
            BMP280_OSAMPLE_4,
            BMP280_OSAMPLE_8,
            BMP280_OSAMPLE_16,
        ]:
            raise ValueError("Invalid mode")

        if i2c is None:
            raise ValueError("An I2C object is required")

        self._mode = mode
        self._device = Device(address, i2c)
        self.t_fine = 0

        chip_id = self._device.readU8(BMP280_REGISTER_CHIPID)
        if chip_id != 0x58:
            raise ValueError("BMP280 not found. Chip ID: 0x{:02X}".format(chip_id))

        self._load_calibration()

        # ctrl_meas:
        # temp oversampling = mode
        # pressure oversampling = mode
        # normal mode = 3
        ctrl_meas = (self._mode << 5) | (self._mode << 2) | 3
        self._device.write8(BMP280_REGISTER_CONTROL, ctrl_meas)

    def _load_calibration(self):
        self.dig_T1 = self._device.readU16LE(BMP280_REGISTER_DIG_T1)
        self.dig_T2 = self._device.readS16LE(BMP280_REGISTER_DIG_T2)
        self.dig_T3 = self._device.readS16LE(BMP280_REGISTER_DIG_T3)

        self.dig_P1 = self._device.readU16LE(BMP280_REGISTER_DIG_P1)
        self.dig_P2 = self._device.readS16LE(BMP280_REGISTER_DIG_P2)
        self.dig_P3 = self._device.readS16LE(BMP280_REGISTER_DIG_P3)
        self.dig_P4 = self._device.readS16LE(BMP280_REGISTER_DIG_P4)
        self.dig_P5 = self._device.readS16LE(BMP280_REGISTER_DIG_P5)
        self.dig_P6 = self._device.readS16LE(BMP280_REGISTER_DIG_P6)
        self.dig_P7 = self._device.readS16LE(BMP280_REGISTER_DIG_P7)
        self.dig_P8 = self._device.readS16LE(BMP280_REGISTER_DIG_P8)
        self.dig_P9 = self._device.readS16LE(BMP280_REGISTER_DIG_P9)

    def read_raw_temp(self):
        msb = self._device.readU8(BMP280_REGISTER_TEMP_DATA)
        lsb = self._device.readU8(BMP280_REGISTER_TEMP_DATA + 1)
        xlsb = self._device.readU8(BMP280_REGISTER_TEMP_DATA + 2)
        raw = ((msb << 16) | (lsb << 8) | xlsb) >> 4
        return raw

    def read_raw_pressure(self):
        msb = self._device.readU8(BMP280_REGISTER_PRESSURE_DATA)
        lsb = self._device.readU8(BMP280_REGISTER_PRESSURE_DATA + 1)
        xlsb = self._device.readU8(BMP280_REGISTER_PRESSURE_DATA + 2)
        raw = ((msb << 16) | (lsb << 8) | xlsb) >> 4
        return raw

    def read_temperature(self):
        adc = self.read_raw_temp()

        var1 = (((adc >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = (((((adc >> 4) - self.dig_T1) * ((adc >> 4) - self.dig_T1)) >> 12) * self.dig_T3) >> 14

        self.t_fine = var1 + var2
        temp = (self.t_fine * 5 + 128) >> 8
        return temp  # hundredths of a degree C

    def read_pressure(self):
        # Must read temperature first so t_fine is updated
        self.read_temperature()

        adc = self.read_raw_pressure()
        var1 = self.t_fine - 128000
        var2 = var1 * var1 * self.dig_P6
        var2 = var2 + ((var1 * self.dig_P5) << 17)
        var2 = var2 + (self.dig_P4 << 35)
        var1 = (((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) >> 12))
        var1 = (((1 << 47) + var1) * self.dig_P1) >> 33

        if var1 == 0:
            return 0

        p = 1048576 - adc
        p = (((p << 31) - var2) * 3125) // var1
        var1 = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25
        var2 = (self.dig_P8 * p) >> 19
        p = ((p + var1 + var2) >> 8) + (self.dig_P7 << 4)

        return p  # Q24.8 Pa

    @property
    def temperature(self):
        t = self.read_temperature()
        ti = t // 100
        td = t % 100
        return "{}.{:02d}C".format(ti, td)

    @property
    def pressure(self):
        p = self.read_pressure() // 256  # Pa
        pi = p // 100
        pd = p % 100
        return "{}.{:02d}hPa".format(pi, pd)
