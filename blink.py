import time
import board # type:ignore
import digitalio # type:ignore

led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()

while True:
    led.value = not led.value
    time.sleep(.25)
    led.value = not led.value
    time.sleep(.25)
    print("Hello")
