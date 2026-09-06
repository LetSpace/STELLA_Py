import os
import time

import microcontroller # type:ignore
import board # type:ignore
import analogio # type:ignore
import digitalio # type:ignore
import busio # type:ignore
import sdcardio # type:ignore
import storage # type:ignore

print(f"Initializing STELLA 2025.1 ...")
import xbee as xbee_lib

import adafruit_gps # type:ignore

import adafruit_bmp3xx # type:ignore

import adafruit_ads1x15.ads1015 as ADS # type:ignore
from adafruit_ads1x15.analog_in import AnalogIn # type:ignore
import adafruit_bno08x
from adafruit_bno08x.i2c import BNO08X_I2C # type:ignore
from adafruit_lsm6ds import Rate, AccelRange, GyroRange
from adafruit_lsm6ds.lsm6dso32 import LSM6DSO32 # type:ignore

# mahony filter for hig ahrs
import gamblor21_ahrs.mahoney

######### DIGITAL PINS ########################################################
print(f"{"Digital Pins":.<20}", end="")
led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()
pyro1out = digitalio.DigitalInOut(board.GP3)
pyro1out.switch_to_output()
pyro1out.value = 0
pyro2out = digitalio.DigitalInOut(board.GP13)
pyro2out.switch_to_output()
pyro2out.value = 0
pyro3out = digitalio.DigitalInOut(board.GP14)
pyro3out.switch_to_output()
pyro3out.value = 0
pyro4out = digitalio.DigitalInOut(board.GP15)
pyro4out.switch_to_output()
pyro4out.value = 0
buzzer = digitalio.DigitalInOut(board.GP5)
buzzer.switch_to_output()
buzzer.value = 0
bno_rst = digitalio.DigitalInOut(board.GP8)
bno_rst.switch_to_output()
bno_rst.value = 1
gps_boot = digitalio.DigitalInOut(board.GP22)
gps_boot.switch_to_input() # effectively floating, per ublox datasheet
print("OK")

######### ANALOG PINS #########################################################
print(f"{"Analog Pins":.<20}", end="")
# PWM mode = cleaner power supply = cleaner ADC readings (datasheet pg17)
smpsmode = digitalio.DigitalInOut(board.SMPS_MODE)
smpsmode.switch_to_output()
smpsmode.value = 1

vsyspin = analogio.AnalogIn(board.VOLTAGE_MONITOR)
sepsense2pin = analogio.AnalogIn(board.A0)
sepsense1pin = analogio.AnalogIn(board.A1)
armsensepin = analogio.AnalogIn(board.A2)

analogConst = 3.3 / 65535 # to convert raw value to actual voltage

def vsys():
    """The voltage on the Vsys pin."""
    return vsyspin.value * analogConst * 3

def sepsense1():
    """Returns the brigness in percent (0 to 1) on sense channel 1."""
    return sepsense1pin.value / 65535

def sepsense2():
    """Returns the brigness in percent (0 to 1) on sense channel 2."""
    return sepsense2pin.value / 65535

def armsense():
    """Returns the current voltage after the arm switch."""
    return armsensepin.value * analogConst * 2

print("OK")

######### GPS #################################################################
print(f"{"GPS":.<20}", end="")
# Based on example: https://docs.circuitpython.org/projects/gps/en/latest/examples.html
gps_uart = busio.UART(tx=board.GP20, rx=board.GP21, baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(gps_uart, debug=False)
# gps.send_command(b"PMTK314,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0") # just GGA
# gps.send_command(b"PMTK220,1000") # 1hz
# Ublox GPS doesn't accept PMTK messages for some reason, but it defaults to all messages, once/sec

def test_gps():
    while True:
        data = gps.read(32)  # read up to 32 bytes
        if data is not None:
            data_string = "".join([chr(b) for b in data])
            print(data_string, end="")

print("OK")

######### XBEE ################################################################
print(f"{"XBee Radio":.<20}", end="")
xbee_uart = busio.UART(tx=board.GP0, rx=board.GP1, baudrate=115200)
xbee_rst = digitalio.DigitalInOut(board.GP2)
xbee_rst.switch_to_output(drive_mode=digitalio.DriveMode.OPEN_DRAIN) # Open-Drain per datasheet
xbee_rst.value = 0

xbee = None
try:
    xbee = xbee_lib.XBee(xbee_uart, xbee_rst)
    print("OK")
except TimeoutError:
    try:
        xbee = xbee_lib.XBee(xbee_uart, xbee_rst)
        print("OK")
    except TimeoutError:
        try:
            xbee = xbee_lib.XBee(xbee_uart, xbee_rst)
            print("OK")
        except TimeoutError:
            print("No XBee found.")

######### SPI BUS #############################################################
print(f"{"SPI Bus":.<20}", end="")
spi = busio.SPI(clock=board.GP18, MOSI=board.GP19, MISO=board.GP16)
sd_cs = board.GP17
bmp_cs = digitalio.DigitalInOut(board.GP11)

bmp_cs.switch_to_output()
bmp_cs.value = 1

print("OK")

######### SD ##################################################################
print(f"{"SD Card":.<20}", end="")
# Must be setup before other modules on SPI bus.
# See: https://learn.adafruit.com/micropython-hardware-sd-cards/tdicola-circuitpython
try:
    sdcard = sdcardio.SDCard(spi, sd_cs)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, "/sd")
    print("OK")
except OSError:
    print("No SD card found.")

######### ALTIMETER ###########################################################
print(f"{"BMP3XX Altimeter":.<20}", end="")
try:
    bmp = adafruit_bmp3xx.BMP3XX_SPI(spi, bmp_cs)
    bmp.sea_level_pressure = 29.92 * 33.86389 # inHg to hPa
    bmp.pressure_oversampling = 32
    bmp.temperature_oversampling = 2
    bmp.filter_coefficient = 16

    def setslp(value):
        bmp.sea_level_pressure = value * 33.86389 # inHg to hPa
    
    print("OK")
except RuntimeError:
    print("No BMP3XX found.")

def test_bmp():
    while True:
        print(f"Alt:{bmp.altitude:.2f}m, Tmp:{bmp.temperature:.2f}C")
        time.sleep(1)

######### I2C BUS #############################################################
print(f"{"I2C Bus":.<20}", end="")
try:
    i2c = busio.I2C(scl=board.GP7, sda=board.GP6)
    print("OK")

######### ADC #################################################################
    print(f"{"ADS1015 ADC":.<20}", end="")
    try:
        adc = ADS.ADS1015(i2c)
        pyro1sensepin = AnalogIn(adc, ADS.P0)
        pyro2sensepin = AnalogIn(adc, ADS.P1)
        pyro3sensepin = AnalogIn(adc, ADS.P2)
        pyro4sensepin = AnalogIn(adc, ADS.P3)

        def pyromath(pin):
            vd = pin.voltage * 2
            if vd == 0:
                return float('inf')
            else:
                return armsense() / (vd / 112) - 112

        def pyro1sense():
            """Returns the resistance on pyro channel 1."""
            return pyromath(pyro1sensepin)

        def pyro2sense():
            """Returns the resistance on pyro channel 2."""
            return pyromath(pyro2sensepin)

        def pyro3sense():
            """Returns the resistance on pyro channel 3."""
            return pyromath(pyro3sensepin)

        def pyro4sense():
            """Returns the resistance on pyro channel 4."""
            return pyromath(pyro4sensepin)
        
        print("OK")
    except Exception as e:
        print("No ADS found. " + str(e))

######### BNO (MAIN) ##########################################################
    print(f"{"BNO08X IMU":.<20}", end="")
    try:
        bno = BNO08X_I2C(i2c)
        bno.enable_feature(adafruit_bno08x.BNO_REPORT_GRAVITY)
        bno.enable_feature(adafruit_bno08x.BNO_REPORT_GYROSCOPE)
        bno.enable_feature(adafruit_bno08x.BNO_REPORT_GEOMAGNETIC_ROTATION_VECTOR)
        bno.enable_feature(adafruit_bno08x.BNO_REPORT_ACCELEROMETER)
        print("OK")
    except Exception as e:
        print("No BNO found. " + str(e))

    def test_bno():
        while True:
            print(bno.gravity)
            time.sleep(1)

######### LSM (HIGH G) ########################################################
    print(f"{"LSM6DSO32 IMU":.<20}", end="")
    try:
        hig = LSM6DSO32(i2c)
        hig.reset()
        hig.accelerometer_range = AccelRange.RANGE_32G
        hig.gyro_range = GyroRange.RANGE_2000_DPS
        hig.accelerometer_data_rate = Rate.RATE_1_66K_HZ
        hig.gyro_data_rate = Rate.RATE_1_66K_HZ
        # set up the ahrs mahony filter for orientation data
        hig_ahrs_filter_samplerate = 1
        hig_ahrs_filter = mahony.Mahony(50, 5, hig_ahrs_filter_samplerate)
        print("OK")
    except Exception as e:
        print("No LSM found. " + str(e))
    
    def test_hig():
        while True:
            print(hig.gyro)
            print(hig.acceleration)
            update_hig()
            print(hig_pitch)
            print(hig_roll)
            print(hig_yaw)
            time.sleep(0.5)
        
    def update_hig():
        hig_ahrs_filter.update(hig.gyro[0], hig.gyro[1], hig.gyro[2], hig.acceleration[0], hig.acceleration[1], hig.acceleration[2], 0, 0, 0)

    def hig_pitch():
        return hig_ahrs_filter.pitch

    def hig_roll():
        return hig_ahrs_filter.hig_roll

    def hig_yaw():
        return hig_ahrs_filter.yaw



except RuntimeError:
    print("Bad I2C bus.")

print("Initialized.")