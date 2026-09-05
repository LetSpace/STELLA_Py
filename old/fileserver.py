import os
import time

import board
import digitalio
import busio
import sdcardio
import storage

import wifi
import ipaddress
import mdns
import socketpool
import adafruit_httpserver as http

spi = busio.SPI(clock=board.GP10, MOSI=board.GP11, MISO=board.GP12)
sd_cs = board.GP14
bmp_cs = digitalio.DigitalInOut(board.GP18)
icm_cs = digitalio.DigitalInOut(board.GP15)
nrfl_cs = digitalio.DigitalInOut(board.GP13)
nrfl_ce = digitalio.DigitalInOut(board.GP9)

bmp_cs.switch_to_output()
bmp_cs.value = 1
icm_cs.switch_to_output()
icm_cs.value = 1
nrfl_cs.switch_to_output()
nrfl_cs.value = 1

sdcard = sdcardio.SDCard(spi, sd_cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, '/sd')

if wifi.radio.ap_active:
    print("AP already running.")
else:
    print("Starting AP")
    wifi.radio.start_ap("STELA01", "password")
print(f"SSID: STELA01\nPassword: password")

# Server
pool = socketpool.SocketPool(wifi.radio)
http.MIMETypes.configure(
    default_to="text/plain",
    keep_for=[".html", ".css", ".js"]
    # Everything not in ^this^ list removed to save memory
)
server = http.Server(pool, "/sd", debug=True)

@server.route("/")
def logs(request: http.Request):
    with open("/web/logs.html") as f:
        content = ""
        for fname in os.listdir("/sd"):
            content = content + f'<div><a href="/{fname}" download>{fname}</a></div>\n'
        html = f.read().format(content=content)

        return http.Response(request, html, content_type="text/html")

server.serve_forever(str(wifi.radio.ipv4_address_ap))