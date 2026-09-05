from helpers import *
import digitalio
import board

led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()
led.value = 0

def thing():
    print("the 3 one")
    led.value = 1

newTimer(3, thing)
newTimer(2, lambda: print("the 2 one"))
newTimer(2.5, lambda: print("the 2.5 one"))
newTimer(1, lambda: print("the 1 one"))

while True:
    updateTimers()