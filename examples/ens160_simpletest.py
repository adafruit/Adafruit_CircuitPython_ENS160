# SPDX-FileCopyrightText: Copyright (c) 2022 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import time
import board
import adafruit_ens160

i2c = board.I2C()  # uses board.SCL and board.SDA

from adafruit_debug_i2c import DebugI2C
debug_i2c = DebugI2C(i2c)

ens = adafruit_ens160.ENS160(debug_i2c)

ens.mode = adafruit_ens160.MODE_STANDARD
curr_mode = ens.mode
print("Current mode: ", end='')
if curr_mode == adafruit_ens160.MODE_SLEEP:
    print("Sleeping")
if curr_mode == adafruit_ens160.MODE_IDLE:
    print("Idle")
if curr_mode == adafruit_ens160.MODE_STANDARD:
    print("Standard sensing")

# Set the temperature compensation variable to the ambient temp
# for best sensor calibration
ens.temperature_compensation = 25
print("Current temperature compensation = %0.1f *C" % ens.temperature_compensation)
# Same for ambient relative humidity
ens.humidity_compensation = 50
print("Current rel humidity compensation = %0.1f %%" % ens.humidity_compensation)

while True:
    #print("data ready?", ens.new_data_available)

    status = ens.data_validity
    if status == adafruit_ens160.NORMAL_OP:
        print("Normal operation")
    if status == adafruit_ens160.WARM_UP:
        print("Warming up")
    if status == adafruit_ens160.START_UP:
        print("Initial startup")
    if status == adafruit_ens160.INVALID_OUT:
        print("Invalid output")
    time.sleep(1)

    print("AQI (1-5):", ens.AQI)
    print("TVOC (ppb):", ens.TVOC)
    print("eCO2 (ppm):", ens.eCO2)
