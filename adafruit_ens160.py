# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2022 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_ens160`
================================================================================

CircuitPython / Python library for ScioSense ENS160 digital multi-gas sensor


* Author(s): ladyada

Implementation Notes
--------------------

**Hardware:**

.. todo:: Add links to any specific hardware product page(s), or category page(s).
  Use unordered list & hyperlink rST inline format: "* `Link Text <url>`_"

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

.. todo:: Uncomment or remove the Bus Device and/or the Register library dependencies
  based on the library's use of either.

# * Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
# * Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

import time
from micropython import const
from adafruit_bus_device import i2c_device
from adafruit_register.i2c_struct import ROUnaryStruct, UnaryStruct
from adafruit_register.i2c_bit import ROBit
from adafruit_register.i2c_bits import ROBits

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_ENS160.git"


ENS160_I2CADDR_DEFAULT: int = const(0x53)  # Default I2C address

_ENS160_REG_PARTID = const(0x00)
_ENS160_REG_OPMODE = const(0x10)

_ENS160_REG_TEMPIN = const(0x13)
_ENS160_REG_RHIN = const(0x15)

_ENS160_REG_STATUS = const(0x20)
_ENS160_REG_AQI = const(0x21)
_ENS160_REG_TVOC = const(0x22)
_ENS160_REG_ECO2 = const(0x24)
                         
MODE_SLEEP = 0x00
MODE_IDLE = 0x01
MODE_STANDARD = 0x02
_valid_modes = (MODE_SLEEP, MODE_IDLE, MODE_STANDARD)

NORMAL_OP = 0x00
WARM_UP = 0x01
START_UP = 0x02
INVALID_OUT = 0x03

class ENS160:
    """Driver for the ENS160 air quality sensor
    :param ~busio.I2C i2c_bus: The I2C bus the ENS160 is connected to.
    :param address: The I2C device address. Defaults to :const:`0x53`
    """

    part_id = ROUnaryStruct(_ENS160_REG_PARTID, "<H")
    _mode = UnaryStruct(_ENS160_REG_OPMODE, "<B")
    _temp_in = UnaryStruct(_ENS160_REG_TEMPIN, "<H")
    _rh_in = UnaryStruct(_ENS160_REG_RHIN, "<H")

    new_data_available = ROBit(_ENS160_REG_STATUS, 1)
    data_validity = ROBits(2, _ENS160_REG_STATUS, 2)
    AQI = ROBits(2, _ENS160_REG_AQI, 0)
    TVOC = ROUnaryStruct(_ENS160_REG_TVOC, "<H")
    eCO2 = ROUnaryStruct(_ENS160_REG_ECO2, "<H")
    
    def __init__(self, i2c_bus, address=ENS160_I2CADDR_DEFAULT):
        # pylint: disable=no-member
        self.i2c_device = i2c_device.I2CDevice(i2c_bus, address)

        if self.part_id != 0x160:
            raise RuntimeError("Unable to find ENS160, check your wiring")

        self.mode = MODE_STANDARD

    @property
    def mode(self):
        """Operational Mode, can be MODE_SLEEP, MODE_IDLE, or MODE_STANDARD"""
        return self._mode

    @mode.setter
    def mode(self, newmode):
        if not newmode in _valid_modes:
            raise RuntimeError("Invalid mode: must be MODE_SLEEP, MODE_IDLE, or MODE_STANDARD")
        self._mode = newmode


    @property
    def temperature_compensation(self):
        """Temperature compensation setting, set this to ambient temperature
        to get best gas sensor readings, floating point degrees C"""
        return (self._temp_in / 64.0) - 273.15

    @temperature_compensation.setter
    def temperature_compensation(self, temp_c):
        self._temp_in = int((temp_c +  273.15) * 64.0 + 0.5)
    
    @property
    def humidity_compensation(self):
        """Humidity compensation setting, set this to ambient relative
        humidity (percentage 0-100) to get best gas sensor readings"""
        return self._rh_in / 512.0

    @humidity_compensation.setter
    def humidity_compensation(self, hum_perc):
        self._rh_in = int(hum_perc * 512 + 0.5)
