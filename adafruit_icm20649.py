# The MIT License (MIT)
#
# Copyright (c) 2019 Bryan Siepert for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_icm20649`
================================================================================

Library for the ST ICM-20649 Wide-Range 6-DoF Accelerometer and Gyro

* Author(s): Bryan Siepert

Implementation Notes
--------------------

**Hardware:**

.. todo:: Add links to any specific hardware product page(s), or category page(s). Use unordered list & hyperlink rST
   inline format: "* `Link Text <url>`_"

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases


* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
* Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_ICM20649.git"
# Common imports; remove if unused or pylint will complain
from time import sleep
import adafruit_bus_device.i2c_device as i2c_device

from adafruit_register.i2c_struct import UnaryStruct, ROUnaryStruct, Struct
from adafruit_register.i2c_struct_array import StructArray
from adafruit_register.i2c_bit import RWBit
from adafruit_register.i2c_bits import RWBits



_ICM20649_DEFAULT_ADDRESS = 0x68 #icm20649 default i2c address
_ICM20649_DEVICE_ID = 0xE1

# Bank 0
_ICM20649_WHO_AM_I = 0x00  # device_id register
_ICM20649_REG_BANK_SEL = 0x7F # register bank selection register
_ICM20649_PWR_MGMT_1  = 0x06 #primary power management register
_ICM20649_ACCEL_XOUT_H = 0x2D # first byte of accel data

# Bank 2
_ICM20649_ACCEL_SMPLRT_DIV_1 = 0x10
_ICM20649_ACCEL_SMPLRT_DIV_2 = 0x11
_ICM20649_ACCEL_CONFIG_1     = 0x14


#TODO: CV-ify
# GYRO_FS:
# Sensitivity Scale Factor GYRO_FS_SEL = 0 65.5 LSB/(dps) 1
# GYRO_FS_SEL = 1 32.8 LSB/(dps) 1
# GYRO_FS_SEL = 2 16.4 LSB/(dps) 1
# GYRO_FS_SEL = 3 8.2 LSB/(dps) 1

#ACCEL_FS:
# ACCEL_FS = 0 8,192 LSB/g 1
# ACCEL_FS = 1 4,096 LSB/g 1
# ACCEL_FS = 2 2,048 LSB/g 1
# ACCEL_FS = 3 1,024 LSB/g 1

# Accel DLPF Bandwidth CV:
# 000 = 246 Hz / 1209 Hz if FCHOICE is 0
# 001 = 246 Hz
# 010 = 111.4 Hz
# 011 = 50.4 Hz
# 100 = 23.9 Hz
# 101 = 11.5 Hz
# 110 = 5.7 Hz
# 111 = 473 Hz

G_TO_ACCEL           = 9.80665

class ICM20649:
    """Library for the ST ICM-20649 Wide-Range 6-DoF Accelerometer and Gyro.

        :param ~busio.I2C i2c_bus: The I2C bus the ICM20649 is connected to.
        :param address: The I2C slave address of the sensor

    """

    _device_id = ROUnaryStruct(_ICM20649_WHO_AM_I, "<B")
    _bank = RWBits(2, _ICM20649_REG_BANK_SEL, 4)
    _reset = RWBit(_ICM20649_PWR_MGMT_1, 7)
    _sleep = RWBit(_ICM20649_PWR_MGMT_1, 6)
    _clock_source = RWBits(3, _ICM20649_PWR_MGMT_1, 0)

    _accel_dlpf_enable = RWBits(1, _ICM20649_ACCEL_CONFIG_1, 0)
    _accel_scale = RWBits(2, _ICM20649_ACCEL_CONFIG_1, 1)
    _accel_dlpf_config = RWBits(3, _ICM20649_ACCEL_CONFIG_1, 3)
    # this value is a 12-bit register spread across two bytes, big-endian first
    _accel_rate_divisor = UnaryStruct(_ICM20649_ACCEL_SMPLRT_DIV_1,">H" )

    # readByte(ICM20649_ADDR, ACCEL_XOUT_H , buf, 6);
    _raw_accel_data = Struct(_ICM20649_ACCEL_XOUT_H, ">hhh")




    def __init__(self, i2c_bus, address=_ICM20649_DEFAULT_ADDRESS):
        self.i2c_device = i2c_device.I2CDevice(i2c_bus, address)

        if self._device_id != _ICM20649_DEVICE_ID:
            print("found device id: ", self._device_id)
            raise RuntimeError("Failed to find ICM20649 - check your wiring!")
        self.reset()

    def reset(self):

        self._bank = 0
        self._sleep = False        

        # //switch to user bank 2
        self._bank = 2
        
        # /* Configure the accelerometer */

        # SET DEFAULT RANGE
        self._accel_scale = 1 # 8G; default is 4G
        self._accel_dlpf_enable = True

        #TODO: CV-ify
        self._accel_dlpf_config = 3

        
        # 1.125 kHz/(1+ACCEL_SMPLRT_DIV[11:0]), 
        # 1125Hz/(1+20) = 53.57Hz
        self._accel_rate_divisor = 20 


        # writeByte(ICM20649_ADDR,GYRO_CONFIG_1, gyroConfig);
        # delay(100); // 60 ms + 1/ODR
        # // ODR =  1.1kHz/(1+GYRO_SMPLRT_DIV[7:0]) => 100 ?
        # writeByte(ICM20649_ADDR,GYRO_SMPLRT_DIV, 0x0A); // Set gyro sample rate divider

        # //reset to register bank 0
        # writeByte(ICM20649_ADDR,REG_BANK_SEL, 0x00);
        # return true;
        # back to bank 0 as the default
        self._bank = 0

    
    @property
    def acceleration(self):
        """Acceleration!"""
        raw_accel_data = self._raw_accel_data

        x = self._scale_xl_data(raw_accel_data[0])
        y = self._scale_xl_data(raw_accel_data[1])
        z = self._scale_xl_data(raw_accel_data[2])

        return(x, y, z)

    # @property
    # def gyro(self):
    #     """ME GRYO, ME FLY PLANE"""
    #     raw_gyro_data = self._raw_gyro_data
    #     x = self._scale_gyro_data(raw_gyro_data[0])
    #     y = self._scale_gyro_data(raw_gyro_data[1])
    #     z = self._scale_gyro_data(raw_gyro_data[2])

    #     return (x, y, z)

    # def _scale_xl_data(self, raw_measurement):
    #     return raw_measurement * AccelRange.lsb[self._cached_accel_range] * _MILLI_G_TO_ACCEL
    def _scale_xl_data(self, raw_measurement):
        return raw_measurement/ 4096 * G_TO_ACCEL # hard coded to 8G range


    # def _scale_gyro_data(self, raw_measurement):
    #     return raw_measurement * GyroRange.lsb[self._cached_gyro_range] / 1000

    @property
    def accel_data_rate(self):
    # http://43zrtwysvxb2gf29r5o0athu-wpengine.netdna-ssl.com/wp-content/uploads/2016/06/DS-000192-ICM-20649-v1.0.pdf , page 65
    # 1.125 kHz/(1+ACCEL_SMPLRT_DIV[11:0]), 
    # 1125Hz/(1+20) = 53.57Hz
    # self._accel_rate_divisor = 20 
        
        pass