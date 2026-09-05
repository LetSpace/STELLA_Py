import os
import wifi # type:ignore
import socketpool # type:ignore
import adafruit_httpserver as http

import lib.stella24hw as stella
from helpers import *

pool = socketpool.SocketPool(wifi.radio)
http.MIMETypes.configure(
    default_to="text/plain",
    keep_for=[".html"]
    # Everything not in ^this^ list removed to save memory
)
server = http.Server(pool, "/sd", debug=True)

@server.route("/")
def base(request: http.Request):
    with open("/web/status.html") as f:
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

def start():
    if wifi.radio.ipv4_address_ap is not None:
        server.start(str(wifi.radio.ipv4_address_ap))
    else:
        server.start(str(wifi.radio.ipv4_address))
    
