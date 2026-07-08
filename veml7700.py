from machine import I2C

class VEML7700:
    ADDRESS = 0x10

    # Registers
    ALS_CONF_0 = 0x00
    ALS_WH = 0x01
    ALS_WL = 0x02
    POWER_SAVING = 0x03
    ALS = 0x04
    WHITE = 0x05
    INTERRUPT = 0x06

    # Gain settings
    GAIN_1 = 0x00
    GAIN_2 = 0x01
    GAIN_1_8 = 0x02
    GAIN_1_4 = 0x03

    # Integration times
    IT_25MS = 0x0C
    IT_50MS = 0x08
    IT_100MS = 0x00
    IT_200MS = 0x01
    IT_400MS = 0x02
    IT_800MS = 0x03

    def __init__(self, i2c, address=ADDRESS, gain=GAIN_1, it=IT_100MS):
        self.i2c = i2c
        self.address = address
        self.gain = gain
        self.it = it
        self._write_config()

    def _write_reg(self, reg, value):
        data = bytearray(2)
        data[0] = value & 0xFF
        data[1] = (value >> 8) & 0xFF
        self.i2c.writeto_mem(self.address, reg, data)

    def _read_reg(self, reg):
        data = self.i2c.readfrom_mem(self.address, reg, 2)
        return data[0] | (data[1] << 8)

    def _write_config(self):
        # Shutdown bit = 0 (powered on)
        # Interrupt disabled
        conf = (self.gain << 11) | (self.it << 6)
        self._write_reg(self.ALS_CONF_0, conf)

    def power_on(self):
        conf = self._read_reg(self.ALS_CONF_0)
        conf &= ~(1 << 0)
        self._write_reg(self.ALS_CONF_0, conf)

    def power_off(self):
        conf = self._read_reg(self.ALS_CONF_0)
        conf |= (1 << 0)
        self._write_reg(self.ALS_CONF_0, conf)

    def read_als_raw(self):
        return self._read_reg(self.ALS)

    def read_white_raw(self):
        return self._read_reg(self.WHITE)

    def _resolution(self):
        # Base lux per count at Gain=1, IT=100ms
        res = 0.0576

        # Adjust for gain
        if self.gain == self.GAIN_2:
            res /= 2
        elif self.gain == self.GAIN_1_4:
            res *= 4
        elif self.gain == self.GAIN_1_8:
            res *= 8

        # Adjust for integration time
        if self.it == self.IT_25MS:
            res *= 4
        elif self.it == self.IT_50MS:
            res *= 2
        elif self.it == self.IT_100MS:
            pass
        elif self.it == self.IT_200MS:
            res /= 2
        elif self.it == self.IT_400MS:
            res /= 4
        elif self.it == self.IT_800MS:
            res /= 8

        return res

    def lux(self):
        raw = self.read_als_raw()
        lux = raw * self._resolution()
        return lux

    def white(self):
        raw = self.read_white_raw()
        white = raw * self._resolution()
        return white