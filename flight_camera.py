import os
import traceback
import time
import struct
import microcontroller # type:ignore

from lib.helpers import *

import lib.stella25hw as stella

# LED on for 3 seconds:
stella.led.value = 1

def ledoff():
    stella.led.value = 0

newTimer(3, ledoff)

######### SETTINGS ############################################################
# set in /settings.toml
stagenum = os.getenv("stagenum") # 1 is booster, 2 is sustainer
isprimary = os.getenv("isprimary") == "True" # convert string "True" to boolean
radiotype = os.getenv("radiotype")
if stagenum == None or isprimary == None or radiotype == None:
    raise ValueError("Empty or invalid settings.toml file")

# TODO Update from simulation
stella.setslp(29.92)
main_deploy_alt = 152 # m (500ft)
sus_ignition_min_alt = 240 # m (800ft)
sus_ignition_min_vel = 15 # m/s (40fps)
sus_ignition_max_angle = 30 # deg
sus_ignition_delay = 2 # coast in seconds between booster burnout and sustainer ignition
sus_ignition_watchdog = sus_ignition_delay + 10 # if no thrust after this long, give up, recovery

camera_power = stella.pyro3out
sustainer_pyro = stella.pyro4out
drogue_pyro = stella.pyro1out
main_pyro = stella.pyro2out

GND_XBEE_ID = 0x0013A200_424A8065

######### MAIN LOOP ###########################################################
# find the next available filename
logno = 0
for f in os.listdir("/sd"):
    if f.startswith("flightlog"):
        try:
            # 0        9
            # flightlog001.csv
            logno = max(logno, int(f[9:12]))
        except ValueError:
            continue

logno += 1
logfilename = f"/sd/flightlog{logno:03d}.csv"
log = DataLogger(logfilename, [
    "time", "endtime",
    "state",
    "pyro1", "pyro2", "pyro3", "pyro4",
    "pyro1r", "pyro2r", "pyro3r", "pyro4r", 
    "vbatt", "varm", "sepsense1", "sepsense2", "cputemp",
    "lat", "lon", "gpsalt", "fixq", "hdop", "gps_s_count",
    "baro", "temp",
    "vvel",
    "accel_x", "accel_y", "accel_z",
    "gyro_x", "gyro_y", "gyro_z",
    "orient_x", "orient_y", "orient_z", "orient_w",
    "tilt",
    "hig_x", "hig_y", "hig_z", 
    "msg"
])

_STATE_IDLE = 1
_STATE_ARMFAIL = 10 # armed laying down
_STATE_ARMED = 2    # arm switch closed, light on, choose zero
_STATE_BOOST = 3    # up 20m + 3gs
_STATE_GAP = 4      # UPPERSTAGEONLY: accel_y goes neg
_STATE_SUSWARMUP = 5# UPPERSTAGEONLY: delay and safe
_STATE_SUSTAIN = 6  # UPPERSTAGEONLY: 3gs
_STATE_COAST = 7    # accel_y goes neg
_STATE_DROGUE = 8   # passed apogee, down 5m from max
_STATE_MAIN = 9     # (main_deploy_alt)m AGL
state = _STATE_IDLE

ground = 0
maxalt = 0

# can_tx prevents both radios from transmitting at once. The "talking stick" is
# passed back and forth after each set of packets via a handoff packet
if isprimary:
    can_tx = True
else:
    can_tx = False
last_handoff = time.monotonic()

gap_started = 0

gps_s_count = 0
errors = []

def buzzon():
    stella.buzzer.value = 1
def buzzoff():
    stella.buzzer.value = 0

last_buzzer_toggle = 0
last_log = time.monotonic()

prev_agl = 0
prev_agl_time = 0

camera_state = 0

try:
    while True:
        try:
            if stella.gps.update():
                gps_s_count += 1
            
            updateTimers()
            maxalt = max(maxalt, stella.bmp.altitude)

            ###  UP is -Y  ###
            accelup = -stella.hig.acceleration[1]
            tilt = angleBtwn(stella.bno.gravity, (0, -9.8, 0))
            agl = stella.bmp.altitude - ground  # Above Ground Level

            t = time.monotonic()
            vvel = (agl - prev_agl) / (t - prev_agl_time) # m/s
            prev_agl = agl
            prev_agl_time = t

            # Update Camera
            camera_power.value = camera_state

        except Exception as e:
            s = f"{type(e)} in intro: {e}"
            if s not in errors:
                errors.append(s)

        try:
            if state == _STATE_IDLE:
                if stella.armsense() > 2:
                    if stagenum == 2 and tilt > 30:
                        state = _STATE_ARMFAIL
                        buzzon()
                    else:
                        stella.led.value = 1
                        buzzon()
                        newTimer(0.5, buzzoff)
                        ground = stella.bmp.altitude
                        maxalt = stella.bmp.altitude # reset
                        state = _STATE_ARMED # state change last, so if there's an error, this block gets retried

            elif state == _STATE_ARMFAIL:
                if stella.armsense() < 2:
                    state = _STATE_IDLE
                    buzzoff()

            elif state == _STATE_ARMED:
                camera_power.value = 1 # Turn the camera on when armed
                if agl > 20 and accelup > 30: # 20m and 3g
                    state = _STATE_BOOST
                elif stella.armsense() < 2: # disarmed
                    stella.led.value = 0
                    buzzon()
                    newTimer(0.5, buzzoff)
                    state = _STATE_IDLE

            elif state == _STATE_BOOST:
                if accelup < 0: # negative accel along thrust axis (not boosting anymore)
                    if stagenum == 1: # First Stage starts coast
                        maxalt = stella.bmp.altitude # reset
                        state = _STATE_COAST
                    elif stagenum == 2: # Upper Stage starts ignition delay
                        # No Stage Separation. Hot staging

                        gap_started = time.monotonic()
                        state = _STATE_GAP

            elif state == _STATE_GAP:
                # wait for ignition delay
                if time.monotonic() - gap_started > sus_ignition_delay:
                    if agl > sus_ignition_min_alt and vvel > sus_ignition_min_vel and tilt < sus_ignition_max_angle: # high enough, fast enough, and straight enough
                        # Sustainer Ignition
                        def sustainer_on():
                            sustainer_pyro.value = 1
                        def sustainer_off():
                            sustainer_pyro.value = 0

                        if isprimary:
                            sustainer_on() # turn on now
                            newTimer(2, sustainer_off) # turn off after 2 seconds
                        else: # Backup
                            newTimer(1, sustainer_on) # turn on after 1 second
                            newTimer(3, sustainer_off) # turn off after 2 more seconds

                        state = _STATE_SUSWARMUP
                    else:
                        # Abort ignition
                        maxalt = stella.bmp.altitude # reset
                        state = _STATE_COAST

            elif state == _STATE_SUSWARMUP:
                if accelup > 30:
                    state = _STATE_SUSTAIN
                elif time.monotonic() - gap_started > sus_ignition_watchdog: # give up
                    maxalt = stella.bmp.altitude # reset
                    state = _STATE_COAST

            elif state == _STATE_SUSTAIN:
                # same as BOOST
                if accelup < 0:
                    maxalt = stella.bmp.altitude # reset
                    state = _STATE_COAST

            elif state == _STATE_COAST:
                # Check for sustainer ignition. If abort, ignition may have happened anyway from the stage sep charge
                if accelup > 30:
                    state = _STATE_SUSTAIN

                elif stella.bmp.altitude < maxalt - 5: # 5m below max
                    def drogue_on():
                        drogue_pyro.value = 1
                    def drogue_off():
                        drogue_pyro.value = 0

                    if isprimary:
                        drogue_on()
                        newTimer(2, drogue_off) # turn off after 2 seconds
                    else: # Backup
                        newTimer(1, drogue_on) # turn on after 1 second
                        newTimer(3, drogue_off) # turn off after 2 more seconds

                    state = _STATE_DROGUE
                    #TODO: watch for sep?

            elif state == _STATE_DROGUE:
                if agl <= main_deploy_alt:
                    def main_on():
                        main_pyro.value = 1
                    def main_off():
                        main_pyro.value = 0

                    if isprimary:
                        main_on()
                        newTimer(2, main_off) # turn off after 2 seconds
                    else: # Backup
                        newTimer(1, main_on) # turn on after 1 second
                        newTimer(3, main_off) # turn off after 2 more seconds

                    state = _STATE_MAIN

            elif state == _STATE_MAIN:
                def camera_off():
                    camera_power.value = 0
                newTimer(60, camera_off) # Turn the camera off after 60 s
                if time.monotonic() - last_buzzer_toggle > 1:
                    stella.buzzer.value = not stella.buzzer.value
                    last_buzzer_toggle = time.monotonic()
                

        except Exception as e:
            s = f"{type(e)} in STATE TRANSITION: {e}"
            if s not in errors:
                errors.append(s)

        # LOGGING
        currenttime = time.monotonic()
        if currenttime >= last_log + 0.1:
            last_log = currenttime
            
            log.values = {}

            # State
            log.values["time"] = currenttime
            log.values["state"] = state
            log.values["pyro1"] = stella.pyro1out.value
            log.values["pyro2"] = stella.pyro2out.value
            log.values["pyro3"] = stella.pyro3out.value
            log.values["pyro4"] = stella.pyro4out.value

            # Analog
            try:
                log.values["vbatt"] = stella.vsys()
                log.values["varm"] = stella.armsense()
                log.values["pyro1r"] = stella.pyro1sense()
                log.values["pyro2r"] = stella.pyro2sense()
                log.values["pyro3r"] = stella.pyro3sense()
                log.values["pyro4r"] = stella.pyro4sense()
                log.values["sepsense1"] = stella.sepsense1()
                log.values["sepsense2"] = stella.sepsense2()
                log.values["cputemp"] = microcontroller.cpu.temperature
            except Exception as e:
                errors.append(f"{type(e)} in ANALOG: {e}")

            # GPS
            try:
                log.values["lat"] = stella.gps.latitude
                log.values["lon"] = stella.gps.longitude
                log.values["gpsalt"] = stella.gps.altitude_m
                log.values["fixq"] = stella.gps.fix_quality
                log.values["hdop"] = stella.gps.hdop
                log.values["gps_s_count"] = gps_s_count
                gps_s_count = 0
            except Exception as e:
                errors.append(f"{type(e)} in GPS: {e}")

            # Altimeter
            try:
                log.values["baro"] = stella.bmp.altitude
                log.values["temp"] = stella.bmp.temperature
                log.values["vvel"] = vvel
            except Exception as e:
                errors.append(f"{type(e)} in ALTIMETER: {e}")

            # LSM (HIGH G)
            try:
                hig_accel = stella.hig.acceleration
                log.values["hig_x"] = hig_accel[0]
                log.values["hig_y"] = hig_accel[1]
                log.values["hig_z"] = hig_accel[2]
            except Exception as e:
                errors.append(f"{type(e)} in IMU: {e}")

            # BNO
            try:
                accel = stella.bno.acceleration
                gyro = stella.bno.gyro
                orient = stella.bno.geomagnetic_quaternion
                log.values["gyro_x"] = gyro[0]
                log.values["gyro_y"] = gyro[1]
                log.values["gyro_z"] = gyro[2]
                log.values["accel_x"] = accel[0]
                log.values["accel_y"] = accel[1]
                log.values["accel_z"] = accel[2]
                log.values["orient_x"] = orient[0]
                log.values["orient_y"] = orient[1]
                log.values["orient_z"] = orient[2]
                log.values["orient_w"] = orient[3]
                log.values["tilt"] = tilt
            except Exception as e:
                errors.append(f"{type(e)} in BNO: {e}")

            log.values["endtime"] = time.monotonic()
            log.values["msg"] = ";".join(errors)
            errors = []
            log.write_to_file()


            # check for transmission from other Stella
            if radiotype == "xbee":
                try:
                    frame = stella.xbee.poll(stella.xbee.RECEIVE_PACKET)
                    if frame != None:
                        payload = frame[15:-1] # get elements 15..last-1 because the received data has an offset of 15
                        if payload[1] == 5: # is a handoff packet
                            can_tx = True # my turn
                            # print("Received handoff")
                        elif payload[1] == 4: # is a ground command packet
                            print(f'Ground command received: {payload}')
                except Exception as e:
                    print(f"Error recieving handoff: {e}")

            if can_tx:
                start_timer = time.monotonic_ns()  # start timer

                if radiotype == "nrfl":
                    data = struct.pack(">fbffffff",
                        log.values.get("time", float('-inf')),
                        log.values.get("state", -1),
                        log.values.get("pyro1r", float('-inf')),
                        log.values.get("pyro2r", float('-inf')),
                        log.values.get("vbatt", float('-inf')),
                        log.values.get("varm", float('-inf')),
                        log.values.get("baro", float('-inf')),
                        log.values.get("hig_x", float('-inf')),
                    )
                    stella.nrf.send(data)

                elif radiotype == "xbee":
                    # SENSOR DATA               |        |     |        |      
                    data = struct.pack(">ffbbbbbffffffffffffbfbfffffffffffffffff",
                        log.values.get("time", float('-inf')),
                        log.values.get("endtime", float('-inf')),
                        log.values.get("state", -1),
                        log.values.get("pyro1", -1),
                        log.values.get("pyro2", -1),
                        log.values.get("pyro3", -1),
                        log.values.get("pyro4", -1),

                        log.values.get("pyro1r", float('-inf')),
                        log.values.get("pyro2r", float('-inf')),
                        log.values.get("pyro3r", float('-inf')),
                        log.values.get("pyro4r", float('-inf')),
                        log.values.get("vbatt", float('-inf')),
                        log.values.get("varm", float('-inf')),
                        log.values.get("sepsense1", float('-inf')),
                        log.values.get("sepsense2", float('-inf')),
                        log.values.get("cputemp", float('-inf')),

                        log.values.get("lat", float('-inf')) or float('-inf'),
                        log.values.get("lon", float('-inf')) or float('-inf'),
                        log.values.get("gpsalt", float('-inf')) or float('-inf'),
                        log.values.get("fixq", -1) or -1,
                        log.values.get("hdop", float('-inf')) or float('-inf'),
                        log.values.get("gps_s_count", -1),

                        log.values.get("baro", float('-inf')),
                        log.values.get("temp", float('-inf')),
                        log.values.get("vvel", float('-inf')),
                        log.values.get("accel_x", float('-inf')),
                        log.values.get("accel_y", float('-inf')),
                        log.values.get("accel_z", float('-inf')),
                        log.values.get("gyro_x", float('-inf')),
                        log.values.get("gyro_y", float('-inf')),
                        log.values.get("gyro_z", float('-inf')),

                        log.values.get("orient_x", float('-inf')),
                        log.values.get("orient_y", float('-inf')),
                        log.values.get("orient_z", float('-inf')),
                        log.values.get("orient_w", float('-inf')),
                        log.values.get("tilt", float('-inf')),
                        log.values.get("hig_x", float('-inf')),
                        log.values.get("hig_y", float('-inf')),
                        log.values.get("hig_z", float('-inf'))
                    )

                    # Header Format:
                    # Sender: "A" or "B"
                    # packet type: 1-Data, 2-Msg, 4-Ground Command, 5-Handoff
                    # packet number in sequence

                    # SENSOR DATA
                    header = struct.pack(">bbb", ord("A" if isprimary else "B"), 1, 0)
                    payload = header + data
                    stella.xbee.transmit_request(GND_XBEE_ID, payload, wait_for_response=False)

                    # ERROR MESSAGES
                    data = log.values.get("msg")
                    if len(data) > 0:
                        data = data.encode()
                        header = struct.pack(">bbb", ord("A" if isprimary else "B"), 2, 0)
                        payload = header + data
                        stella.xbee.transmit_request(GND_XBEE_ID, payload, wait_for_response=False)
                    
                    # HANDOFF
                    header = struct.pack(">bbb", ord("A" if isprimary else "B"), 5, 0)
                    stella.xbee.transmit_request(stella.xbee.BCAST_ADDR, header, wait_for_response=False)

                    can_tx = False
                    last_handoff = time.monotonic()

                end_timer = time.monotonic_ns()  # end timer
                print(f"Transmitted in {(end_timer - start_timer) / 1000000}ms")
            else:
                if time.monotonic() - last_handoff > 0.5:
                    # handed off 1 sec ago and it never came back
                    can_tx = True
                    print("No Handoff")


except Exception as e:
    traceback.print_exception(e)
    with open("/sd/problems.txt", "a") as f:
        f.write(f"{logno}:\n{"".join(traceback.format_exception(e))}\n")
        f.flush()
    with open(logfilename, "a") as logfile:
        logfile.write("ERR")
        logfile.flush()
