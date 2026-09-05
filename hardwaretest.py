import os
import gc
import time
import wifi # type:ignore
import socketpool # type:ignore
import lib.adafruit_httpserver as http

from lib.helpers import *
import lib.stella24hw as stella

print(gc.mem_free())
gc.collect()
print(gc.mem_free())

######### WiFi AP #############################################################
if wifi.radio.ap_active:
    print("AP already running.")
else:
    print("Starting AP")
    wifi.radio.start_ap("STELLA_2A", "password")
print(f"SSID: STELLA_2A\nPassword: password")

######### Web Server ##########################################################
pool = socketpool.SocketPool(wifi.radio)
http.MIMETypes.configure(
    default_to="text/plain",
    keep_for=[".html"]
    # Everything not in ^this^ list removed to save memory
)
server = http.Server(pool, "/sd", debug=True)

@server.route("/")
def base(request: http.Request):
    with open("/web/chargetest.html") as f:
        html = f.read().format(
            vsys=f"{stella.vsys():.3f}",
            varm=f"{stella.armsense():.3f}",
            p1=f"{stella.pyro1sense():.3f}",
            p2=f"{stella.pyro2sense():.3f}",
            p3=f"{stella.pyro3sense():.3f}",
            p4=f"{stella.pyro4sense():.3f}",
            sense1=f"{stella.sepsense1():.1%}",
            sense2=f"{stella.sepsense2():.1%}",
        )

        return http.Response(request, html, content_type="text/html")

@server.route("/logs")
def logs(request: http.Request):
    with open("/web/logs.html") as f:
        content = ""
        i = 0
        for fname in reversed(os.listdir("/sd")):
            content = content + f'<div><a href="/{fname}" download>{fname}</a>\t{prettybytes(os.stat("/sd/" + fname)[6])}</div>\n'
            i += 1
            if i > 20: # only get the last 20 files. Without this. pi runs out of memory
                break
        
        stat = os.statvfs('/sd')
        totalspace = stat[1] * stat[2]
        freespace = stat[1] * stat[3]
        html = f.read().format(
            content=content,
            freespace=prettybytes(freespace),
            totalspace=prettybytes(totalspace),
        )

        return http.Response(request, html, content_type="text/html")

@server.route("/fire1")
def fire1(request: http.Request):
    stella.led.value = 1

    for i in range(3):
        stella.buzzer.value = 1
        time.sleep(0.5)
        stella.buzzer.value = 0
        time.sleep(0.5)

    stella.pyro1out.value = 1
    time.sleep(1)
    stella.led.value = 0
    stella.pyro1out.value = 0

    return http.Redirect(request, "/")

@server.route("/fire2")
def fire1(request: http.Request):
    stella.led.value = 1

    for i in range(3):
        stella.buzzer.value = 1
        time.sleep(0.5)
        stella.buzzer.value = 0
        time.sleep(0.5)

    stella.pyro2out.value = 1
    time.sleep(1)
    stella.led.value = 0
    stella.pyro2out.value = 0

    return http.Redirect(request, "/")

@server.route("/fire3")
def fire1(request: http.Request):
    stella.led.value = 1

    for i in range(3):
        stella.buzzer.value = 1
        time.sleep(0.5)
        stella.buzzer.value = 0
        time.sleep(0.5)

    stella.pyro3out.value = 1
    time.sleep(1)
    stella.led.value = 0
    stella.pyro3out.value = 0

    return http.Redirect(request, "/")

@server.route("/fire4")
def fire1(request: http.Request):
    stella.led.value = 1

    for i in range(3):
        stella.buzzer.value = 1
        time.sleep(0.5)
        stella.buzzer.value = 0
        time.sleep(0.5)

    stella.pyro4out.value = 1
    time.sleep(1)
    stella.led.value = 0
    stella.pyro4out.value = 0

    return http.Redirect(request, "/")

server.serve_forever(str(wifi.radio.ipv4_address_ap))
