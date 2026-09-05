"""
Simple example of using the RF24 class.
"""
import time
import struct
import board # type:ignore
from digitalio import DigitalInOut  # type:ignore
import busio  # type:ignore

from circuitpython_nrf24l01.rf24 import RF24  # type:ignore

SPI_BUS = busio.SPI(clock=board.GP10, MOSI=board.GP11, MISO=board.GP12)
CE_PIN = DigitalInOut(board.GP5)
CSN_PIN = DigitalInOut(board.GP13)

nrf = RF24(SPI_BUS, CSN_PIN, CE_PIN)

nrf.pa_level = -12
# nrf.channel = 8

# set RX address of TX node into an RX pipe
nrf.open_rx_pipe(0, b"STELA")

try:
    nrf.listen = True  # put radio into RX mode and power up
    print("time,state,pyro1out,pyro2out,vbatt,armsw,pyro1vd,pyro2vd,pyro1r,pyro2r,cputemp,lat,lon,gpsalt,fixq,hdop,,sats,gps_s_count,baro,temp,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z")

    frame = [",,,,", ",,", ",,", ",", ",,,,,", ",", ",,", ",,"] # 5 3 3 2 6 2 3 3
    last_packet_no = -1

    while True:
        if nrf.available():
            packet = nrf.read().decode("ascii")

            packet_no = int(packet[0])
            if packet_no <= last_packet_no: # TODO: Add timing?
                print(",".join(frame))
                frame = [",,,,", ",,", ",,", ",", ",,,,,", ",", ",,", ",,"] # 5 3 3 2 6 2 3 3
            frame[packet_no] = packet[2:]

            last_packet_no = packet_no

except KeyboardInterrupt:
    print(" Keyboard Interrupt detected. Powering down radio...")
    nrf.power = False
