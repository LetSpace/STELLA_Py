import board
import busio
import digitalio

import stella24hw as stella
import helpers

# Break on tx line to force command mode
print("BREAK")
stella.xbee_uart.deinit()
uart = busio.UART(rx=board.GP13, baudrate=9600)
txline = digitalio.DigitalInOut(board.GP12)
txline.switch_to_output()
txline.value = 0

# wait for ok
try:
    while True:
        c = uart.read(1)
        if c is not None:
            print(c.decode("utf-8"), end="")
except KeyboardInterrupt:
    print("END BREAK")

uart.deinit()
txline.deinit()
uart = busio.UART(tx=board.GP12, rx=board.GP13, baudrate=9600)

while True:
    try:
        while True:
            c = uart.read(1)
            if c is not None:
                print(c.decode("utf-8"), end="")
    except KeyboardInterrupt:
        line = input("\n>")
        line = helpers.parseescapes(line)
        line = bytes(line, "utf-8")

        uart.write(line)

            
