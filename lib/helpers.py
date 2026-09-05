import time
import math

class Timer:
  def __init__(self, t, action):
    self.t = t
    self.action = action
    self.starttime = time.monotonic()

  def update(self, currenttime):
    if currenttime >= self.starttime + self.t:
        self.action()
        return True
    else:
        return False

timers = []

def newTimer(seconds, action):
    '''Will call the passed function after the given number of seconds. updateTimers() must be called regularly for this to work.'''
    timers.append(Timer(seconds, action))

def updateTimers():
    '''Checks all running timers, and calls the function on any that have expired.'''
    global timers
    currenttime = time.monotonic()

    dones = []
    for timer in timers:
        if timer.update(currenttime):
            dones.append(timer)
    timers = [x for x in timers if x not in dones]

class CircularBuffer:
    def __init__(self, size, default=0):
        self.size = size
        self.values = [default] * size
        self.i = 0
    
    def __str__(self):
        return ", ".join([str(val) for val in self.values])

    def __iter__(self):
        self.iteri = 0
        return self

    def __next__(self):
        if self.iteri >= self.size:
            raise StopIteration
        else:
            val = self.values[self.iteri]
            self.iteri += 1
            return val

    def append(self, value):
        self.values[self.i] = value
        self.i += 1
        self.i %= self.size

class DataLogger:
    def __init__(self, filename, value_names):
        self.filename = filename
        self.value_names = value_names
        self.values = {}

        # Header
        with open(filename, "a") as logfile:
            logfile.write(",".join(value_names) + "\n")
    
    def write_to_file(self):
        with open(self.filename, "a") as logfile:
            for name in self.value_names:
                if name in self.values:
                    v = self.values[name]
                    if isinstance(v, float):
                        v = f"{v:.3f}"
                    elif isinstance(v, bool):
                        v = int(v)
                    logfile.write(str(v))
                logfile.write(",")
            logfile.write("\n")
            logfile.flush()

def prettybytes(n):
    g = 2**30
    if n > g:
        return f"{n/g:.3f}GB"
    
    m = 2**20
    if n > m:
        return f"{n/m:.3f}MB"

    k = 2**10
    if n > k:
        return f"{n/k:.3f}KB"
    
    return f"{n}B"

def parseescapes(string):
    output = ""
    escaping = False
    for c in string:
        if escaping:
            if c == "n" or c == "N":
                output = output + "\n"
            elif c == "r" or c == "R":
                output = output + "\r"

            escaping = False
            continue

        if c == "\\":
            escaping = True
            continue

        output = output + c
    
    return output


def angleBtwn(a, b):
    dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    return math.degrees(math.acos(dot / (vectorMagnitude(a) * vectorMagnitude(b))))

def vectorMagnitude(a):
    return math.sqrt(math.pow(a[0], 2) + math.pow(a[1], 2) + math.pow(a[2], 2))