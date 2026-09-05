import time
from lib.helpers import *

import lib.stella24hw as stella

def buzzon():
    stella.buzzer.value = 1
def buzzoff():
    stella.buzzer.value = 0

newTimer(3, buzzon)
newTimer(3.05, buzzoff)
newTimer(3.1, buzzon)
newTimer(3.15, buzzoff)

newTimer(0, buzzon)
newTimer(.5, buzzoff)

while True:
    updateTimers()