import os
import gc
import time
import wifi # type:ignore
import socketpool # type:ignore
import lib.adafruit_httpserver as http

from lib.helpers import *
import lib.stella25hw as stella

gc.collect()

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

server.serve_forever(str(wifi.radio.ipv4_address_ap))
