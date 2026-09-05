"""
Simple example of using the RF24 class.
"""
import time
import struct
import board
import digitalio
import busio

from circuitpython_nrf24l01.rf24 import RF24

######### SPI BUS #############################################################
spi = busio.SPI(clock=board.GP10, MOSI=board.GP11, MISO=board.GP12)
sd_cs = digitalio.DigitalInOut(board.GP14)
bmp_cs = digitalio.DigitalInOut(board.GP18)
icm_cs = digitalio.DigitalInOut(board.GP15)
nrfl_cs = digitalio.DigitalInOut(board.GP13)
nrfl_ce = digitalio.DigitalInOut(board.GP9)

sd_cs.switch_to_output()
sd_cs.value = 1
bmp_cs.switch_to_output()
bmp_cs.value = 1
icm_cs.switch_to_output()
icm_cs.value = 1
nrfl_cs.switch_to_output()
nrfl_cs.value = 1
nrfl_ce.switch_to_output()
nrfl_ce.value = 0
###############################################################################

nrf = RF24(spi, nrfl_cs, nrfl_ce)

nrf.pa_level = -12
# nrf.channel = 8

nrf.auto_ack = False

# set TX address of RX node into the TX pipe
nrf.open_tx_pipe(b"STELA")  # always uses pipe 0

try:
    count = 5  # count = 5 will only transmit 5 packets
    nrf.listen = False  # ensures the nRF24L01 is in TX mode

    while count:
        # use struct.pack to structure your data
        # into a usable payload
        buffer = b"Hello, World!"
        start_timer = time.monotonic_ns()  # start timer
        result = nrf.send(buffer)
        end_timer = time.monotonic_ns()  # end timer
        if not result:
            print("send() failed or timed out")
        else:
            print(
                "Transmission successful! Time to Transmit:",
                "{} us. Sent: {}".format((end_timer - start_timer) / 1000, str(buffer)),
            )
        time.sleep(1)
        count -= 1

except KeyboardInterrupt:
    print(" Keyboard Interrupt detected. Powering down radio...")
    nrf.power = False
