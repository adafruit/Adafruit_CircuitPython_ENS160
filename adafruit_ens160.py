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

* `ScioSense ENS160 multi-gas sensor <http://www.adafruit.com/products/5606>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
* Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

import struct
import time

from adafruit_bus_device import i2c_device
from adafruit_register.i2c_bit import ROBit, RWBit
from adafruit_register.i2c_bits import ROBits
from adafruit_register.i2c_struct import ROUnaryStruct, UnaryStruct
from micropython import const

try:
    from typing import Dict, List, Optional, Union

    from busio import I2C
    from typing_extensions import Literal
except ImportError:
    pass

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_ENS160.git"


ENS160_I2CADDR_DEFAULT: int = const(0x53)  # Default I2C address

_ENS160_REG_PARTID = const(0x00)
_ENS160_REG_OPMODE = const(0x10)
_ENS160_REG_CONFIG = const(0x11)
_ENS160_REG_COMMAND = const(0x12)
_ENS160_REG_TEMPIN = const(0x13)
_ENS160_REG_RHIN = const(0x15)
_ENS160_REG_STATUS = const(0x20)
_ENS160_REG_AQI = const(0x21)
_ENS160_REG_TVOC = const(0x22)
_ENS160_REG_ECO2 = const(0x24)
_ENS160_REG_GPRREAD = const(0x48)

MODE_SLEEP = 0x00
MODE_IDLE = 0x01
MODE_STANDARD = 0x02
MODE_RESET = 0xF0
_valid_modes = (MODE_SLEEP, MODE_IDLE, MODE_STANDARD, MODE_RESET)

NORMAL_OP = 0x00
WARM_UP = 0x01
START_UP = 0x02
INVALID_OUT = 0x03

COMMAND_NOP = 0x00
COMMAND_CLRGPR = 0xCC
COMMAND_GETAPPVER = 0x0E


class ENS160:
    """Driver for the ENS160 air quality sensor

    :param ~busio.I2C i2c_bus: The I2C bus the ENS160 is connected to.
    :param int address: The I2C device address. Defaults to :const:`0x53`
    """

    part_id = ROUnaryStruct(_ENS160_REG_PARTID, "<H")
    _mode = UnaryStruct(_ENS160_REG_OPMODE, "<B")
    _temp_in = UnaryStruct(_ENS160_REG_TEMPIN, "<H")
    _rh_in = UnaryStruct(_ENS160_REG_RHIN, "<H")
    _status = UnaryStruct(_ENS160_REG_STATUS, "<B")

    # sensor data registers
    command = UnaryStruct(_ENS160_REG_COMMAND, "<B")
    _new_GPR_available = ROBit(_ENS160_REG_STATUS, 0)
    _new_data_available = ROBit(_ENS160_REG_STATUS, 1)
    data_validity = ROBits(2, _ENS160_REG_STATUS, 2)
    AQI = ROBits(2, _ENS160_REG_AQI, 0)
    TVOC = ROUnaryStruct(_ENS160_REG_TVOC, "<H")
    eCO2 = ROUnaryStruct(_ENS160_REG_ECO2, "<H")

    # interrupt register bits
    interrupt_polarity = RWBit(_ENS160_REG_CONFIG, 6)
    interrupt_pushpull = RWBit(_ENS160_REG_CONFIG, 5)
    interrupt_on_GPR = RWBit(_ENS160_REG_CONFIG, 3)
    interrupt_on_data = RWBit(_ENS160_REG_CONFIG, 1)
    interrupt_enable = RWBit(_ENS160_REG_CONFIG, 0)

    def __init__(self, i2c_bus: I2C, address: int = ENS160_I2CADDR_DEFAULT) -> None:
        self.i2c_device = i2c_device.I2CDevice(i2c_bus, address)

        if self.part_id not in {0x160, 0x161}:
            raise RuntimeError("Unable to find ENS160 or ENS161, check your wiring")
        self.clear_command()
        self.mode = MODE_STANDARD
        self._buf = bytearray(8)
        # Buffered readings for when we read all at once
        self._bufferdict = {
            "AQI": None,
            "TVOC": None,
            "eCO2": None,
            "Resistances": [None, None, None, None],
        }
        # Initialize with 'room temperature & humidity'
        self.temperature_compensation = 25
        self.humidity_compensation = 50

    def reset(self) -> None:
        """Perform a soft reset command"""
        self.mode = MODE_RESET
        time.sleep(0.01)

    def clear_command(self) -> None:
        """Clears out custom data"""
        self.command = COMMAND_NOP
        self.command = COMMAND_CLRGPR
        time.sleep(0.01)

    def _read_gpr(self) -> None:
        """Read 8 bytes of general purpose registers into self._buf"""
        self._buf[0] = _ENS160_REG_GPRREAD
        with self.i2c_device as i2c:
            i2c.write_then_readinto(self._buf, self._buf, out_end=1)

    @property
    def new_data_available(self) -> bool:
        """This function is wierd, it checks if there's new data or
        GPR (resistances) and if so immediately reads it into the
        internal buffer... otherwise the status is lost!"""
        # we'll track if we actually read new data!
        newdat = False

        if self._new_data_available:
            self._buf[0] = _ENS160_REG_AQI
            with self.i2c_device as i2c:
                i2c.write_then_readinto(self._buf, self._buf, out_end=1, in_end=5)
            (
                self._bufferdict["AQI"],
                self._bufferdict["TVOC"],
                self._bufferdict["eCO2"],
                _,
                _,
                _,
            ) = struct.unpack("<BHHBBB", self._buf)
            newdat = True

        if self._new_GPR_available:
            self._read_gpr()
            for i, x in enumerate(struct.unpack("<HHHH", self._buf)):
                self._bufferdict["Resistances"][i] = int(pow(2, x / 2048.0))
            newdat = True

        return newdat

    def read_all_sensors(self) -> Dict[str, Optional[Union[int, List[int]]]]:
        """All of the currently buffered sensor information"""
        # return the currently buffered deets
        return self._bufferdict

    @property
    def firmware_version(self) -> str:
        """Read the semver firmware version from the general registers"""
        curr_mode = self.mode
        self.mode = MODE_IDLE
        self.clear_command()
        time.sleep(0.01)
        self.command = COMMAND_GETAPPVER
        self._read_gpr()
        self.mode = curr_mode
        return "%d.%d.%d" % (self._buf[4], self._buf[5], self._buf[6])

    @property
    def mode(self) -> Literal[0, 1, 2, 240]:
        """Operational Mode, can be MODE_SLEEP, MODE_IDLE, MODE_STANDARD, or MODE_RESET"""
        return self._mode

    @mode.setter
    def mode(self, newmode: Literal[0, 1, 2, 240]) -> None:
        if not newmode in _valid_modes:
            raise RuntimeError(
                "Invalid mode: must be MODE_SLEEP, MODE_IDLE, MODE_STANDARD, or MODE_RESET"
            )
        self._mode = newmode

    @property
    def temperature_compensation(self) -> float:
        """Temperature compensation setting, set this to ambient temperature
        to get best gas sensor readings, floating point degrees C"""
        return (self._temp_in / 64.0) - 273.15

    @temperature_compensation.setter
    def temperature_compensation(self, temp_c: float) -> None:
        self._temp_in = int((temp_c + 273.15) * 64.0 + 0.5)

    @property
    def humidity_compensation(self) -> float:
        """Humidity compensation setting, set this to ambient relative
        humidity (percentage 0-100) to get best gas sensor readings"""
        return self._rh_in / 512.0

    @humidity_compensation.setter
    def humidity_compensation(self, hum_perc: float) -> None:
        self._rh_in = int(hum_perc * 512 + 0.5)
